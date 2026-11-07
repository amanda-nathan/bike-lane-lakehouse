# 0001 Iceberg and Trino

The first datasets are small. Boston's daily bike counts are about 3,000 rows, and DuckDB would handle them with less setup.

I'm using Iceberg on S3 with Trino anyway, because of where the project is going:

- The NYC data is bigger. Traffic speeds are 113M rows, bike and pedestrian counts are 21.6M, and the Citi Bike and Bluebikes trip files are tens of GB. Partitioning and file pruning start to matter at that size.
- Several tools need the same tables: the Python loader, dbt, Trino, and an MCP server. Iceberg is an open format, so they all read one copy.
- Some questions need a live source (Bluebikes station status in Postgres) joined to history. Trino can query both without copying either.
- Every load is an Iceberg snapshot, so I can see what a table looked like before a refresh, and sources can add columns without a rewrite.

Downsides: more containers to run locally, and frequent loads leave small files and old snapshots that need scheduled cleanup (`optimize`, `expire_snapshots`). DuckDB can still read the same tables for quick exploration.
