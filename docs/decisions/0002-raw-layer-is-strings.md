# 0002 Raw tables are all strings

The source files are messy. Boston's CSVs start with a byte-order mark, dates look like `6/6/2023 4:00:00.000` (stored in UTC), `bike_pct` is sometimes a percent and sometimes a fraction, and NYC zip codes are sometimes blank. Letting the loader guess types means one odd row can fail a load or turn into a NULL without anyone noticing.

So `bikelake load` writes every column as a string, normalizes column names to snake_case, and adds `_source_url` and `_loaded_at`. Casting and cleanup happen in dbt staging models, where they're tested and reviewed.

Each load overwrites the table, which creates a new snapshot. Older loads can still be queried until the snapshots are expired. New source columns are added to the table schema automatically.

The tradeoff is that querying raw tables directly means a lot of `CAST`. That's fine. The modeled tables are what people should query.
