"""Copy the mart tables to Cloudflare R2 (R2 Data Catalog), for the public version.

Each table keeps its schema and partitioning, and each publish is an Iceberg overwrite,
so the public catalog keeps snapshots too (Cloudflare expires them after 7 days).
"""

import os
from urllib.parse import urlparse

from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NoSuchTableError

from bikelake.load import catalog as local_catalog

NAMESPACE = "marts"


def r2_catalog(read_only: bool = False):
    prefix = "R2_READ_" if read_only else "R2_"
    return load_catalog(
        "r2",
        type="rest",
        uri=os.environ["R2_CATALOG_URI"],
        warehouse=os.environ["R2_WAREHOUSE"],
        token=os.environ[f"{prefix}TOKEN"],
        **{
            "s3.endpoint": os.environ["R2_ENDPOINT"],
            "s3.access-key-id": os.environ[f"{prefix}ACCESS_KEY_ID"],
            "s3.secret-access-key": os.environ[f"{prefix}SECRET_ACCESS_KEY"],
            "s3.region": "auto",
        },
    )


def mart_tables() -> list[str]:
    return sorted(name for _, name in local_catalog().list_tables(NAMESPACE))


def publish(tables: list[str] | None = None) -> dict[str, int]:
    """Overwrite each mart table in R2 with the local copy. Returns rows per table."""
    local, r2 = local_catalog(), r2_catalog()
    r2.create_namespace_if_not_exists(NAMESPACE)
    rows = {}
    for name in tables or mart_tables():
        source = local.load_table(f"{NAMESPACE}.{name}")
        data = source.scan().to_arrow()
        identifier = f"{NAMESPACE}.{name}"
        try:
            target = r2.load_table(identifier)
            with target.update_schema() as update:
                update.union_by_name(source.schema())
        except NoSuchTableError:
            target = r2.create_table(identifier, schema=source.schema(), partition_spec=source.spec())
        target.overwrite(data)
        rows[name] = len(data)
        print(f"published {identifier}: {len(data):,} rows to {urlparse(os.environ['R2_CATALOG_URI']).netloc}")
    return rows
