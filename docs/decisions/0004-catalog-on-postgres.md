# 0004 Iceberg catalog on Postgres

The REST catalog image stores its table pointers in SQLite by default, and SQLite allows one writer at a time. Once dbt built several models in parallel, commits collided and failed with `SQLITE_BUSY`.

The catalog now keeps its pointers in Postgres, in its own `iceberg_catalog` database. The fixture image only ships the SQLite driver, so `catalog/Dockerfile` adds the Postgres JDBC driver, pinned by checksum.

Moving catalogs didn't touch the data. The six existing tables were registered in the new catalog from their current metadata files (`register_table`), which kept every snapshot.

The real version of this decision is which managed catalog to use. On AWS that would be Glue; for the free public version, Cloudflare's R2 Data Catalog. Both speak the same Iceberg REST protocol, so it's a configuration change.
