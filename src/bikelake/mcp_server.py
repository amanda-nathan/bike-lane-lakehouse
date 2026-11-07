"""MCP server: ask questions of the lakehouse through the semantic layer, or with read-only SQL.

    uv run bikelake-mcp                              # stdio, for a local MCP client
    uv run bikelake-mcp --http --port 8000           # streamable HTTP at /mcp

Over HTTP, set MCP_ACCESS_KEY to require `Authorization: Bearer <key>` on every request.
"""

import argparse
import hmac
import os

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from trino.exceptions import TrinoUserError

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
    # Errors go back to the model as text, with MetricFlow's suggestions, so it can fix the query.
    try:
        sql = semantic.compile_sql(metrics, group_by, where, order_by, limit)
    except semantic.InvalidQuery as e:
        return {"error": str(e)}
    try:
        result = warehouse.run(sql)
    except TrinoUserError as e:
        return {"error": e.message, "sql": sql}
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
    try:
        return {**warehouse.run(checked), "sql": checked}
    except TrinoUserError as e:
        return {"error": e.message, "sql": checked}


class RequireAccessKey:
    """Turn away HTTP requests without `Authorization: Bearer <key>` before they reach any tool."""

    def __init__(self, app, key: str):
        self.app = app
        self.expected = f"Bearer {key}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            given = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(given, self.expected):
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"text/plain"), (b"www-authenticate", b"Bearer")]})
                await send({"type": "http.response.body", "body": b"Missing or wrong access key.\n"})
                return
        await self.app(scope, receive, send)


def main() -> None:
    parser = argparse.ArgumentParser(prog="bikelake-mcp")
    parser.add_argument("--http", action="store_true", help="serve streamable HTTP instead of stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if not args.http:
        server.run()
        return

    # Behind a public hostname, accept only requests addressed to it (DNS rebinding protection).
    security = None
    if hosts := [h.strip() for h in os.getenv("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]:
        security = TransportSecuritySettings(
            allowed_hosts=hosts + ["localhost:*", "127.0.0.1:*"],
            allowed_origins=[f"https://{h}" for h in hosts],
        )
    app = server.streamable_http_app(host=args.host, transport_security=security)
    if key := os.getenv("MCP_ACCESS_KEY"):
        app = RequireAccessKey(app, key)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
