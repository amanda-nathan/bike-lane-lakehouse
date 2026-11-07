# CLAUDE.md

Conventions, layout, and commands for this repo. The README covers setup and what the project is; the reasons behind the design are in `docs/decisions/`.

## Layout

```
docker-compose.yml        all services; every port bound to 127.0.0.1
Dockerfile                two targets: app (Dagster, MCP server) and notebook (Jupyter)
catalog/Dockerfile        Iceberg REST catalog plus the Postgres JDBC driver
postgres/init.sql         creates the catalog's database on a fresh volume
.env.example              every secret the stack needs; copy to .env
trino/catalog/            one properties file per Trino catalog; secrets via ${ENV:...}
src/bikelake/
  sources.py              every dataset; the only place URLs live
  extract.py              download to s3://landing/<source>/, one CSV per file
  load.py                 landing -> iceberg.raw.<source>
  stations.py             live GBFS feed -> Postgres station_status
  defs.py                 Dagster: raw assets, dbt assets, checks, schedules
  semantic.py             metric catalog and MetricFlow SQL, read from dbt/target
  warehouse.py            read-only Trino queries and the SQL guard for run_sql
  mcp_server.py           MCP tools
  config.py               endpoints and secrets from the environment
  storage.py              S3 filesystem helper
  cli.py                  bikelake list | extract | load | run | stations
dbt/
  models/staging/         views: types, names, local time, dedupe
  models/intermediate/    tables: lane installs, crash-to-lane spatial join
  models/marts/           tables with enforced contracts; _semantic.yml holds metrics
  tests/                  singular tests
evals/                    questions, run_eval.py, results/, RESULTS.md
docs/charts.py            charts for the README and eval write-up (docs/img)
tests/                    pytest; test_schema_changes needs the stack running
sql/                      example Trino queries, numbered
notebooks/                example notebooks
examples/                 reading the tables without Trino
docs/decisions/           one numbered file per decision
```

## Commands

```bash
docker compose up -d --build                         # start or rebuild everything
docker compose exec trino trino                      # SQL shell
docker compose exec dagster bikelake run             # load all sources without the UI
uv sync                                              # local environment, reads .env
uv run pytest                                        # tests
uv run dagster definitions validate -m bikelake.defs
cd dbt && uv run dbt build --profiles-dir .          # models and tests
cd dbt && uv run dbt parse --profiles-dir .          # refresh dbt/target after editing models or metrics
cd dbt && uv run mf validate-configs                 # check the semantic layer against Trino
cd dbt && uv run mf query --metrics <m> --group-by <d>
uv run bikelake-mcp                                  # MCP server over stdio
uv run --group eval python evals/run_eval.py --dry-run
uv run --group docs python docs/charts.py              # redraw docs/img charts from Trino and eval results
docker compose down                                  # stop, keep data
docker compose down -v                               # stop and delete all data
```

## Conventions

- Raw tables are all strings, with snake_case column names plus `_source_url` and `_loaded_at`. Casting and cleaning belong in dbt staging, not the loader.
- Every load to a raw table is a full overwrite. Don't append to raw tables; history comes from Iceberg snapshots.
- Schema changes from a source must not fail a load: new columns are added, dropped columns stay and are left null.
- To add a source: one `Source` in `sources.py`, its schedule in `SCHEDULES` in `defs.py`, a source entry in `dbt/models/staging/_sources.yml`, a staging model, and a row in the README Data table.
- Staging models are views named `stg_<source>__<entity>`. Marts are tables with enforced contracts; when a mart column changes, update its `data_type` in `_marts.yml`.
- Metrics live in `dbt/models/marts/_semantic.yml`. Anything that would mislead someone reading the number goes in `config.meta.caveats`. Derived ratios cast to double (`cast(x as double) / y`); `* 1.0` keeps Trino in decimals and rounds.
- Before stating a data fact in docs or caveats, check it with a query.
- The MCP server only reads `iceberg.marts`. Keep `warehouse.check_sql` strict and covered by `tests/test_sql_guard.py`.
- Secrets only come from the environment. Never put a password or key in a tracked file. New secrets go in `.env.example` with `change-me`.
- New services bind ports to 127.0.0.1. Services that run a JVM get a `mem_limit`.
- Boston count times are UTC in the source; Bluebikes trip times are local.
- New design decisions get a numbered file in `docs/decisions/`.
- Comments and docs are short and plain. Commit messages are one short line.

## Testing a change

1. `uv run dagster definitions validate -m bikelake.defs`
2. `uv run pytest`
3. dbt changes: `cd dbt && uv run dbt build --profiles-dir .`, and `uv run mf validate-configs` if metrics changed.
4. Loading changes: materialize the affected asset in Dagster and check that its checks pass.
5. MCP changes: rebuild with `docker compose up -d --build mcp` and call a tool.
6. Queries or notebooks: run them, e.g. `docker compose exec -T trino trino < sql/<file>.sql`.
