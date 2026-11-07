# bike-lane-lakehouse

Boston and New York City bike, traffic, and crash data, loaded into Apache Iceberg tables and queried with Trino:

- Storage (`docker-compose.yml`): RustFS, an S3-compatible object store. Downloaded files go in the `landing` bucket as-is; Iceberg tables go in `warehouse`.
- Catalog: the Iceberg REST catalog, which tracks the current metadata file for each table.
- Trino (`trino/catalog/`): queries the Iceberg tables and Postgres, together if needed.
- Loaders (`src/bikelake/`): download each source to `landing`, then load it into `iceberg.raw`.
- Dagster (`src/bikelake/defs.py`): one asset per source, with schedules and checks.
- Postgres: live Bluebikes station status, polled from the public GBFS feed.
- Jupyter (`notebooks/`): querying Trino from Python.

I live near Hyde Park Ave in Roslindale. It has no bike lane, and the City is [looking at a redesign](https://www.boston.gov/departments/transportation/project/hyde-park-avenue-multimodal-corridor). New York publishes the install date of every bike lane along with its crash and traffic data, so it's a good place to look at what changes after a lane goes in. Related: [boston-bike-safety](https://github.com/amanda-nathan/boston-bike-safety), a crash risk model for the same corridor.

See [CLAUDE.md](CLAUDE.md) for conventions, layout, and commands. The reasons behind the design are in [docs/decisions/](docs/decisions/).

## Setup

Only Docker is needed.

1. Clone the repo and create `.env` from the example. Replace each `change-me`, for example with `openssl rand -hex 16`. Passwords and keys live only in `.env`, which git ignores; compose stops with a message if one is missing.
   ```bash
   git clone https://github.com/amanda-nathan/bike-lane-lakehouse
   cd bike-lane-lakehouse
   cp .env.example .env
   ```
2. Start the stack: `docker compose up -d --build`.
3. Load the data. Open Dagster at http://localhost:3000, go to **Catalog**, select all assets, and click **Materialize**. This downloads every source into `landing` and loads it into `iceberg.raw`. It takes about 10 minutes, mostly the NYC crash file.

Every port is bound to 127.0.0.1, so nothing is reachable from other machines on the network. Jupyter has no login for the same reason.

| Service | Address |
|---|---|
| Dagster: runs, schedules, checks | http://localhost:3000 |
| Jupyter: query notebooks | http://localhost:8888 |
| Trino: query monitor | http://localhost:8080 (any username) |
| Storage console | http://localhost:9001/rustfs/console/ (`S3_ACCESS_KEY` / `S3_SECRET_KEY` from `.env`) |

## Schedules

| Asset | Schedule (Eastern) | What runs |
|---|---|---|
| `nyc_crashes` | Daily, 6:00 | Download the full file, overwrite the table |
| `boston_bike_counts_daily`, `boston_bike_counts_hourly`, `boston_crashes`, `nyc_bike_routes` | Mondays, 6:00 | Download the full file, overwrite the table |
| `bluebikes_trips` | 3rd of the month, 6:00 | Download new monthly files only, reload the table from the latest 12 months |
| `station_status` | Hourly | Append one snapshot of every station to Postgres |

**Schedules are off by default.** Turn them on in Dagster under **Automation**.

**Every load replaces the table.** Each overwrite is a new Iceberg snapshot, so earlier loads stay queryable with time travel until snapshots are expired. Expiry isn't scheduled yet.

**Schema changes don't fail a load.** A column the source adds is added to the table. A column the source drops stays in the table and is left null. The `schema_unchanged` check warns when the source adds a column, and `row_count_not_dropped` fails if a load has 5% fewer rows than the one before.

**Raw columns are all strings.** Types are applied in the next layer (dbt, not built yet). See [0002](docs/decisions/0002-raw-layer-is-strings.md).

**Time zones differ by source.** Boston hourly counts are stored in UTC. Bluebikes trip times are local.

**Boston counts are sparse.** Each site is counted for about two days, a few times a year. Compare the same season across years.

## Querying

| How | Command or file |
|---|---|
| SQL shell | `docker compose exec trino trino` |
| Run a SQL file | `docker compose exec -T trino trino < sql/02_live_and_history.sql` |
| Notebook | [notebooks/query_examples.ipynb](notebooks/query_examples.ipynb), in Jupyter or VS Code |
| Without Trino | [examples/read_without_trino.py](examples/read_without_trino.py): PyIceberg and DuckDB on the same table |

[sql/01_first_queries.sql](sql/01_first_queries.sql) covers trends, Iceberg snapshots and files, time travel, and partitioning. [sql/02_live_and_history.sql](sql/02_live_and_history.sql) joins live station status in Postgres to a year of trips in Iceberg, in one query.

## Data

| Table | Source | Rows |
|---|---|---|
| `raw.boston_bike_counts_daily` | [Boston BTD](https://data.boston.gov/dataset/streets-daily-bike-counts) | ~3K |
| `raw.boston_bike_counts_hourly` | [Boston BTD](https://data.boston.gov/dataset/streets-hourly-bike-counts) | ~138K |
| `raw.boston_crashes` | [Boston Vision Zero](https://data.boston.gov/dataset/vision-zero-crash-records) | ~43K |
| `raw.bluebikes_trips` | [Bluebikes](https://bluebikes.com/system-data), latest 12 months | ~4.6M |
| `raw.nyc_bike_routes` | [NYC DOT](https://data.cityofnewyork.us/d/mzxg-pwib) | ~30K |
| `raw.nyc_crashes` | [NYPD](https://data.cityofnewyork.us/d/h9gi-nx95) | ~2.3M |

Sources are defined in `src/bikelake/sources.py`. No data is committed.

## Development

With [uv](https://docs.astral.sh/uv/) installed, `uv sync` sets up a local environment that reads `.env`. `uv run bikelake run` loads every source from the command line, and `uv run pytest` runs the tests, which need the stack running.

## Not built yet

- dbt-trino models: staging, intermediate, marts, with tests
- Larger tables: NYC traffic speeds and Citi Bike trips, partitioned
- Dagster jobs for compaction and snapshot expiry
- Incremental loads for NYC crashes
- Semantic layer with metrics shared across both cities
- MCP server, with an eval comparing semantic layer queries to plain text-to-SQL
- Trino access control and column masking
- CI
- Free public version: Cloudflare R2 and R2 Data Catalog, Trino and MCP on a Hugging Face Space, loads on GitHub Actions
- Kubernetes: Helm install of Trino and Dagster, tested in CI with kind
