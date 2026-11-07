"""MCP server: ask questions of the lakehouse through the semantic layer, or with read-only SQL.

    uv run bikelake-mcp                              # stdio, for a local MCP client
    uv run bikelake-mcp --http --port 8000           # streamable HTTP at /mcp
"""

import argparse

from mcp.server.mcpserver import MCPServer

from bikelake import semantic, warehouse

INSTRUCTIONS = """\
Boston and NYC bike, traffic, and crash data.

Prefer the metrics: call list_metrics, then query_metrics. Metrics carry caveats; pass
them on in your answer, especially sample sizes and comparisons the data can't support.
Use run_sql only when no metric fits, after describe_tables.
"""

server = MCPServer(name="bikelake", instructions=INSTRUCTIONS)


@server.tool()
def list_metrics() -> list[dict]:
    """List every metric with its description, caveats, and the dimensions it can be grouped by.

    Group-by names look like count_day__season or metric_time__month.
    """
    return semantic.metrics()


@server.tool()
def query_metrics(
    metrics: list[str],
    group_by: list[str] | None = None,
    where: list[str] | None = None,
    order_by: list[str] | None = None,
    limit: int | None = None,
) -> dict:
    """Query one or more metrics through the semantic layer.

    Args:
        metrics: Metric names from list_metrics.
        group_by: Dimension names from list_metrics, e.g. ["count_day__count_year"] or ["metric_time__month"].
        where: Filters using MetricFlow syntax, e.g.
            ["{{ Dimension('count_day__season') }} = 'Summer'"] or
            ["{{ TimeDimension('metric_time', 'day') }} >= '2025-01-01'"].
        order_by: Names to sort by; prefix with "-" for descending.
        limit: Maximum rows.

    Returns the rows, the SQL that produced them, and each metric's caveats.
    """
    sql = semantic.compile_sql(metrics, group_by, where, order_by, limit)
    result = warehouse.run(sql)
    return {**result, "sql": sql, "caveats": semantic.caveats_for(metrics)}


@server.tool()
def describe_tables() -> list[dict]:
    """List the queryable tables (iceberg.marts.*) with their columns, types, and descriptions."""
    return semantic.tables()


@server.tool()
def run_sql(sql: str) -> dict:
    """Run one read-only SELECT against iceberg.marts tables (Trino SQL). Results are capped at 1,000 rows."""
    try:
        checked = warehouse.check_sql(sql)
    except warehouse.QueryRejected as e:
        return {"error": str(e)}
    return {**warehouse.run(checked), "sql": checked}


def main() -> None:
    parser = argparse.ArgumentParser(prog="bikelake-mcp")
    parser.add_argument("--http", action="store_true", help="serve streamable HTTP instead of stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.http:
        server.run(transport="streamable-http", host=args.host, port=args.port)
    else:
        server.run()


if __name__ == "__main__":
    main()
