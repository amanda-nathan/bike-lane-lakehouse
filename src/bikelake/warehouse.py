"""Read-only queries against the marts schema in Trino, for the MCP server."""

import os
from datetime import date, datetime
from decimal import Decimal

import sqlglot
import trino
from sqlglot import exp

TRINO_HOST = os.getenv("TRINO_HOST", "localhost")
ALLOWED_SCHEMA = "marts"
MAX_ROWS = 1000
QUERY_TIMEOUT = "30s"


class QueryRejected(ValueError):
    """The SQL isn't a single read-only query against the marts schema."""


def connect():
    return trino.dbapi.connect(
        host=TRINO_HOST,
        port=8080,
        user="mcp",
        catalog="iceberg",
        schema=ALLOWED_SCHEMA,
        session_properties={"query_max_execution_time": QUERY_TIMEOUT},
    )


def check_sql(sql: str) -> str:
    """Allow one SELECT that reads only iceberg.marts tables. Returns the SQL with a row cap."""
    try:
        statements = sqlglot.parse(sql, read="trino")
    except sqlglot.errors.ParseError as e:
        raise QueryRejected(f"Could not parse the SQL: {e}") from e
    statements = [s for s in statements if s is not None]
    if len(statements) != 1:
        raise QueryRejected("Send exactly one statement.")
    query = statements[0]
    if not isinstance(query, exp.Query):
        raise QueryRejected("Only SELECT queries are allowed.")

    cte_names = {cte.alias_or_name for cte in query.find_all(exp.CTE)}
    for table in query.find_all(exp.Table):
        if not table.db and table.name in cte_names:
            continue
        catalog, schema = table.catalog or "iceberg", table.db or ALLOWED_SCHEMA
        if (catalog, schema) != ("iceberg", ALLOWED_SCHEMA):
            raise QueryRejected(f"Only iceberg.{ALLOWED_SCHEMA} tables can be queried, not {table.sql('trino')}.")

    # Cap the query's own LIMIT. Wrapping it in an outer SELECT would drop its ORDER BY in Trino.
    limit = query.args.get("limit")
    if limit is None or not limit.expression.is_int or int(limit.expression.name) > MAX_ROWS:
        query = query.limit(MAX_ROWS)
    return query.sql("trino")


def _jsonable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def run(sql: str) -> dict:
    """Run SQL that has already been checked or generated. Returns columns, rows, and a truncation flag."""
    cur = connect().cursor()
    cur.execute(sql)
    rows = cur.fetchmany(MAX_ROWS + 1)
    columns = [c[0] for c in cur.description]
    return {
        "columns": columns,
        "rows": [[_jsonable(v) for v in row] for row in rows[:MAX_ROWS]],
        "truncated": len(rows) > MAX_ROWS,
    }
