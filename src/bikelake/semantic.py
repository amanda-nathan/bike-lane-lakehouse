"""The dbt semantic layer, for the MCP server: metric catalog, SQL compiled by MetricFlow, table docs.

Reads the artifacts dbt writes to dbt/target (run `dbt parse` after changing models).
"""

import json
import logging
from functools import cache
from pathlib import Path

DBT_DIR = Path(__file__).resolve().parents[2] / "dbt"
TARGET = DBT_DIR / "target"

for name in ("metricflow", "metricflow_semantics", "dbt_metricflow"):
    logging.getLogger(name).setLevel(logging.WARNING)


class InvalidQuery(ValueError):
    """MetricFlow couldn't resolve the request, e.g. an unknown metric or dimension. The message has suggestions."""


@cache
def _engine():
    # Imported here: MetricFlow and dbt take a few seconds to load.
    from dbt_metricflow.cli.cli_configuration import CLIConfiguration

    config = CLIConfiguration()
    config.setup(dbt_profiles_path=DBT_DIR, dbt_project_path=DBT_DIR, configure_file_logging=False)
    return config.mf


@cache
def _semantic_manifest() -> dict:
    return json.loads((TARGET / "semantic_manifest.json").read_text())


@cache
def _manifest() -> dict:
    return json.loads((TARGET / "manifest.json").read_text())


def metrics() -> list[dict]:
    """Every metric with its description, caveats, and the dimensions it can be grouped by."""
    engine = _engine()
    out = []
    for m in sorted(_semantic_manifest()["metrics"], key=lambda m: m["name"]):
        dimensions = engine.simple_dimensions_for_metrics([m["name"]])
        out.append(
            {
                "name": m["name"],
                "label": m["label"],
                "description": m["description"],
                "type": m["type"],
                "caveats": ((m.get("config") or {}).get("meta") or {}).get("caveats", []),
                "group_by": sorted({d.dunder_name for d in dimensions} | {"metric_time__day", "metric_time__month", "metric_time__year"}),
            }
        )
    return out


def caveats_for(metric_names: list[str]) -> dict[str, list[str]]:
    by_name = {m["name"]: m for m in _semantic_manifest()["metrics"]}
    return {
        name: ((by_name[name].get("config") or {}).get("meta") or {}).get("caveats", [])
        for name in metric_names
        if name in by_name
    }


def compile_sql(
    metric_names: list[str],
    group_by: list[str] | None = None,
    where: list[str] | None = None,
    order_by: list[str] | None = None,
    limit: int | None = None,
) -> str:
    from metricflow.engine.metricflow_engine import MetricFlowQueryRequest
    from metricflow_semantics.errors.error_classes import InvalidQueryException

    request = MetricFlowQueryRequest.create(
        metric_names=metric_names,
        group_by_names=group_by or [],
        where_constraints=where or [],
        order_by_names=order_by or [],
        limit=limit,
    )
    try:
        return _engine().explain(request).sql_statement.sql
    except InvalidQueryException as e:
        raise InvalidQuery(str(e)) from e


def tables() -> list[dict]:
    """The marts tables: name, description, and columns with types and descriptions."""
    out = []
    for node in _manifest()["nodes"].values():
        if node["resource_type"] != "model" or node["config"].get("schema") != "marts":
            continue
        if node["name"] == "metricflow_time_spine":
            continue
        out.append(
            {
                "table": f"iceberg.marts.{node['name']}",
                "description": " ".join(node["description"].split()),
                "columns": [
                    {"name": c["name"], "type": c.get("data_type"), "description": c.get("description", "")}
                    for c in node["columns"].values()
                ],
            }
        )
    return sorted(out, key=lambda t: t["table"])
