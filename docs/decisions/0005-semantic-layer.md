# 0005 Metrics in the dbt semantic layer, with caveats

Metrics are defined once in `dbt/models/marts/_semantic.yml` (dbt Semantic Layer spec) and compiled to SQL by MetricFlow, the open-source engine behind it. MetricFlow 0.15 supports Trino.

Each metric can list caveats in `config.meta.caveats`. The MCP server returns them with every result, so an AI client gets the same warnings an analyst would give: Boston counts are two days per location per season, NYC's current year is partial, 29% of NYC crashes have no borough, and so on.

This matters most for the protected lane metrics. Cyclists hurt near new lanes rose 17% while citywide injuries rose 1.7% over the same windows, which reads as "lanes made streets worse" unless you know that lanes go where riding is growing and there's no per-street ridership count to adjust for. That context lives in the metric, not in someone's head.

The MCP server compiles metric queries with MetricFlow and runs the SQL itself on Trino, with a time limit and row cap. Free-form SQL goes through a parser that allows one SELECT on `iceberg.marts` only (see `src/bikelake/warehouse.py`).
