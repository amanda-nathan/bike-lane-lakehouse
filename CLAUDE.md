# CLAUDE.md

Conventions, layout, and commands for this repo. The README covers setup and what the project is; the reasons behind the design are in `docs/decisions/`.

## Layout

```
docker-compose.yml        all services; every port bound to 127.0.0.1
Dockerfile                two targets: app (Dagster) and notebook (Jupyter)
.env.example              every secret the stack needs; copy to .env
trino/catalog/            one properties file per Trino catalog; secrets via ${ENV:...}
src/bikelake/
  sources.py              every dataset; the only place URLs live
  extract.py              download to s3://landing/<source>/, one CSV per file
  load.py                 landing -> iceberg.raw.<source>
  stations.py             live GBFS feed -> Postgres station_status
  defs.py                 Dagster assets, checks, schedules
  config.py               endpoints and secrets from the environment
  storage.py              S3 filesystem helper
  cli.py                  bikelake list | extract | load | run | stations
tests/                    integration tests; need the stack running
sql/                      example Trino queries, numbered
notebooks/                example notebooks; run in the jupyter container or VS Code
examples/                 reading the tables without Trino
docs/decisions/           one numbered file per decision
```

## Commands

```bash
docker compose up -d --build                 # start or rebuild everything
docker compose exec trino trino              # SQL shell
docker compose exec dagster bikelake run     # load all sources without the UI
uv sync                                      # local environment, reads .env
uv run pytest                                # tests
uv run dagster definitions validate -m bikelake.defs
docker compose down                          # stop, keep data
docker compose down -v                       # stop and delete all data
```

## Conventions

- Raw tables are all strings, with snake_case column names plus `_source_url` and `_loaded_at`. Casting and cleaning belong in dbt, not the loader.
- Every load to a raw table is a full overwrite. Don't append to raw tables; history comes from Iceberg snapshots.
- Schema changes from a source must not fail a load: new columns are added, dropped columns stay and are left null.
- To add a source, add one `Source` to `sources.py`, add its schedule to `SCHEDULES` in `defs.py`, and add a row to the Data table in the README. Nothing else should hardcode a URL.
- Secrets only come from the environment. Never put a password or key in a tracked file. New secrets go in `.env.example` with `change-me`.
- New services bind ports to 127.0.0.1.
- Queries against Boston bike counts compare the same season across years. Boston hourly count times are UTC; Bluebikes trip times are local.
- New design decisions get a numbered file in `docs/decisions/`.
- Comments and docs are short and plain. Commit messages are one short line.

## Testing a change

1. `uv run dagster definitions validate -m bikelake.defs`
2. `uv run pytest`
3. If the change touches loading, materialize the affected asset in Dagster and check that both asset checks pass.
4. If it touches queries or notebooks, run them: `docker compose exec -T trino trino < sql/<file>.sql`.
