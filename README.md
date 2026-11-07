# bike-lane-lakehouse

Boston and New York City bike, traffic, and crash data in Apache Iceberg tables, modeled with dbt, scheduled with Dagster, and queried with Trino or by an AI client through MCP.

I live near Hyde Park Ave in Roslindale, which has no bike lane; the City is [looking at a redesign](https://www.boston.gov/departments/transportation/project/hyde-park-avenue-multimodal-corridor). New York publishes when every bike lane went in, so it's a good place to see what changes after one does.

![Cyclists hurt near new NYC protected lanes vs. citywide](docs/img/new_lanes_by_borough.png)

Cyclists hurt near new protected lanes rose 17%, against 1.7% citywide. That doesn't mean the lanes made streets worse: lanes go where riding is growing, and there's no per-street ridership count to adjust for it. Those caveats are attached to the metric, so they come back with every answer built on it.

![Summer bike counts on Washington St in Roslindale](docs/img/washington_street_summers.png)

## Stack

| Piece | Where | What it does |
|---|---|---|
| RustFS | `docker-compose.yml` | S3-compatible storage. `landing` holds files as downloaded; `warehouse` holds Iceberg tables |
| Iceberg REST catalog | `catalog/` | Tracks each table's current metadata. Keeps its pointers in Postgres |
| Trino | `trino/catalog/` | Queries Iceberg and Postgres |
| Loaders | `src/bikelake/` | Download each source, load it into `iceberg.raw` |
| dbt | `dbt/` | Staging, intermediate, and mart models; tests; contracts; metrics with caveats |
| Dagster | `src/bikelake/defs.py` | Loads, dbt models, schedules, and checks in one asset graph |
| MCP server | `src/bikelake/mcp_server.py` | Metrics and read-only SQL for AI clients |
| Eval | `evals/` | Accuracy of semantic-layer queries vs. plain text-to-SQL |

Conventions and commands: [CLAUDE.md](CLAUDE.md). Why it's built this way: [docs/decisions/](docs/decisions/).

## Run it

Needs Docker.

```bash
git clone https://github.com/amanda-nathan/bike-lane-lakehouse
cd bike-lane-lakehouse
cp .env.example .env          # replace each change-me, e.g. with: openssl rand -hex 16
docker compose up -d --build
```

Then open Dagster, go to **Catalog**, select all assets, and click **Materialize**. It takes about 10 minutes, mostly the NYC crash file.

| | |
|---|---|
| Dagster | http://localhost:3000 |
| MCP server | http://localhost:8000/mcp |
| Jupyter | http://localhost:8888 |
| Trino | http://localhost:8080, or `docker compose exec trino trino` |
| Storage console | http://localhost:9001/rustfs/console/ |

Ports are bound to 127.0.0.1 only. To use the MCP server from Claude Code: `claude mcp add --transport http bikelake http://localhost:8000/mcp`.

## Eval

Claude answered questions through the MCP server with SQL tools only, and with the metrics preferred. On hard questions, Opus 5.5 got every answer right either way. Haiku 5.5 got 26 of 30 with SQL only and 29 of 30 with the metrics, mostly because the metric's caveats came along. Two answers I first marked wrong turned out to be better than my answer key. Details and cost: [evals/RESULTS.md](evals/RESULTS.md).

## Data

| Table | Source | Rows |
|---|---|---|
| `raw.boston_bike_counts_daily` | [Boston BTD](https://data.boston.gov/dataset/streets-daily-bike-counts) | ~3K |
| `raw.boston_bike_counts_hourly` | [Boston BTD](https://data.boston.gov/dataset/streets-hourly-bike-counts) | ~138K |
| `raw.boston_crashes` | [Boston Vision Zero](https://data.boston.gov/dataset/vision-zero-crash-records) | ~43K |
| `raw.bluebikes_trips` | [Bluebikes](https://bluebikes.com/system-data), latest 12 months | ~4.6M |
| `raw.nyc_bike_routes` | [NYC DOT](https://data.cityofnewyork.us/d/mzxg-pwib) | ~30K |
| `raw.nyc_crashes` | [NYPD](https://data.cityofnewyork.us/d/h9gi-nx95) | ~2.3M |

Quirks the staging models handle: Boston count times are UTC, Bluebikes times are local; trips across the November clock change end before they start; a few rows are duplicated at the source; NYC route records are versioned. About 29% of NYC crashes have no borough.

Schedules: NYC crashes daily, the other sources weekly, Bluebikes monthly, station status hourly. Each schedule rebuilds only the models downstream of its source. They're off until turned on in Dagster.

## Not built yet

- A mart with one row per crash near a new lane, to fix a double count the eval found
- Larger tables: NYC traffic speeds and Citi Bike trips
- Compaction and snapshot expiry jobs; incremental loads for NYC crashes
- Trino access control and column masking
- CI
- Public version: data on Cloudflare R2, Trino and the MCP server on a Hugging Face Space, loads on GitHub Actions
