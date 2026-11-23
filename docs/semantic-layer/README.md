# The semantic layer, step by step

A semantic layer is a place where each number is defined once, by name. Instead of writing SQL for "bike crashes in Boston", you ask for the metric `boston_bike_crashes`, and the layer writes the SQL. Everyone who asks gets the same definition.

Here it is one file, [`dbt/models/marts/_semantic.yml`](../../dbt/models/marts/_semantic.yml), plus [MetricFlow](https://docs.getdbt.com/docs/build/about-metricflow), the open-source engine that turns a metric request into Trino SQL. This project adds one thing: each metric carries its caveats, and they are returned with every answer.

The results below are from a local copy on 2026-11-23. The numbers change as the data is refreshed.

## 1. Define the metric

Two parts in the same file. A **semantic model** describes a mart table: its time column, the columns you can group by (dimensions), and what you can add up (measures).

```yaml
- name: boston_crashes
  model: ref('fct_boston_crashes')
  defaults:
    agg_time_dimension: crash_date
  dimensions:
    - name: crash_date
      type: time
    - name: mode
      type: categorical
    - name: street
      type: categorical
  measures:
    - name: boston_crash_count
      agg: sum
      expr: "1"
```

A **metric** is a named number built on a measure, with its caveats.

```yaml
- name: boston_bike_crashes
  label: Boston bike crashes
  description: Crashes with an EMS dispatch that involved a person on a bike.
  type: simple
  type_params:
    measure: boston_crash_count
  filter: "{{ Dimension('boston_crash__mode') }} = 'bike'"
  config:
    meta:
      caveats:
        - Based on EMS dispatches, so crashes with no ambulance call are missing.
        - Not directly comparable with NYC crash counts, which come from police reports.
```

There are 26 metrics of three kinds: simple (one measure), ratio (one metric divided by another), and derived (a formula over other metrics).

## 2. See the SQL it writes

This works without the stack running.

```bash
cd dbt && uv run mf query --metrics boston_bike_crashes --group-by metric_time__year --explain
```

```sql
SELECT
  metric_time__year
  , SUM(boston_bike_crashes) AS boston_bike_crashes
FROM (
  SELECT
    DATE_TRUNC('year', crash_date) AS metric_time__year
    , mode AS boston_crash__mode
    , 1 AS boston_bike_crashes
  FROM "iceberg"."marts"."fct_boston_crashes" boston_crashes_src_10000
) subq_2
WHERE boston_crash__mode = 'bike'
GROUP BY
  metric_time__year
```

Nobody wrote that query. The table, the filter, and the time column all came from the definition in step 1.

## 3. Run it

Start Trino (`docker compose up -d trino`) and drop `--explain`.

```bash
cd dbt && uv run mf query --metrics boston_bike_crashes --group-by metric_time__year --order metric_time__year
```

```
metric_time__year      boston_bike_crashes
-------------------  ---------------------
2015-01-01T00:00:00                    502
2016-01-01T00:00:00                    424
2017-01-01T00:00:00                    390
2018-01-01T00:00:00                    425
2019-01-01T00:00:00                    365
2020-01-01T00:00:00                    295
2021-01-01T00:00:00                    239
2022-01-01T00:00:00                    243
2023-01-01T00:00:00                    391
2024-01-01T00:00:00                    366
2025-01-01T00:00:00                    256
```

## 4. An AI client asks the same way

The MCP server ([`src/bikelake/mcp_server.py`](../../src/bikelake/mcp_server.py)) gives an AI client two tools on top of the layer.

`list_metrics` tells it what exists. One entry:

```json
{
 "name": "boston_bike_crashes",
 "label": "Boston bike crashes",
 "description": "Crashes with an EMS dispatch that involved a person on a bike.",
 "type": "simple",
 "caveats": [
  "Based on EMS dispatches, so crashes with no ambulance call are missing.",
  "Not directly comparable with NYC crash counts, which come from police reports."
 ],
 "group_by": [
  "boston_crash__crash_date",
  "boston_crash__mode",
  "boston_crash__street",
  "metric_time__day",
  "metric_time__month",
  "metric_time__year"
 ]
}
```

`query_metrics` runs a request and returns the rows, the SQL, and the caveats. Asking for `new_lane_injury_change`, `citywide_injury_change`, and `new_lane_cyclists_hurt_before`, grouped by `lane_segment__borough`:

| Borough | Change near new lanes | Citywide change, same windows | Cyclists hurt before |
|---|---|---|---|
| Bronx | +32% | -0.5% | 434 |
| Brooklyn | +44% | +1.4% | 931 |
| Manhattan | +0.2% | +2.7% | 2,088 |
| Queens | +22% | +2.1% | 753 |
| Staten Island | +1,200% | +7.2% | 1 |

The same response includes the caveats for `new_lane_injury_change`:

- Always compare with citywide_injury_change over the same windows; citywide injuries changed too.
- Lanes go where riding is growing. More riders after a lane opens means more exposure, and there is no ridership count per street to adjust for it.
- A crash near several adjacent segments counts once per segment.
- Windows after 2020 installs include the pandemic, when riding patterns changed.
- Small groups give extreme percentages (Staten Island has few injuries before). Report new_lane_cyclists_hurt_before next to the change.

Staten Island's +1,200% rests on one injury before. The number alone would mislead; the caveat that comes with it says so.

## 5. A wrong request gets a useful error

Boston crashes have no neighborhood column. Asking to group by `boston_crash__neighborhood` returns an error with suggestions, not a guess:

```
The given input does not match any of the available group-by-items for
SimpleMetric('boston_bike_crashes').

Suggestions:
  [
    'boston_crash__mode',
    'boston_crash__street',
    'boston_crash',
    'boston_crash__crash_date__day',
    'metric_time__day',
  ]
```

The server sends this back to the model as text, so it can fix the request.

## 6. Does it help?

The [eval](../../evals/RESULTS.md) asked the same hard questions two ways: with SQL tools only, and with the metrics preferred. A small model got 26 of 30 with SQL only and 29 of 30 with the metrics, mostly because the caveats came along. A large model got all 30 either way.

Why it's built this way: [docs/decisions/0005-semantic-layer.md](../decisions/0005-semantic-layer.md).
