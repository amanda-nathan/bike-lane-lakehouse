"""Load landed CSVs into Iceberg tables in the raw namespace.

Every column is loaded as a string. Types are applied later in dbt.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.csv as pacsv
from pyiceberg.catalog import load_catalog
from pyiceberg.exceptions import NoSuchTableError

from bikelake import storage
from bikelake.config import CATALOG_PROPS
from bikelake.extract import landing_paths
from bikelake.sources import Source

NAMESPACE = "raw"


def snake(name: str) -> str:
    name = name.replace("﻿", "").strip()
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name)
    name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    return name.strip("_").lower()


def read_csv_as_strings(s3, path: str) -> pa.Table:
    with s3.open_input_stream(path) as f:
        first_line = f.read(1 << 16).decode("utf-8-sig").splitlines()[0]
    names = [snake(h) for h in next(csv.reader(io.StringIO(first_line)))]
    with s3.open_input_stream(path) as f:
        return pacsv.read_csv(
            f,
            read_options=pacsv.ReadOptions(column_names=names, skip_rows=1, block_size=1 << 26),
            parse_options=pacsv.ParseOptions(newlines_in_values=True),
            convert_options=pacsv.ConvertOptions(column_types={n: pa.string() for n in names}),
        )


def catalog():
    return load_catalog("lakehouse", **CATALOG_PROPS)


@dataclass
class LoadResult:
    rows: int
    snapshot_id: int
    added_columns: list[str] = field(default_factory=list)  # new in the source, added to the table
    missing_columns: list[str] = field(default_factory=list)  # in the table, gone from the source


def load(source: Source) -> LoadResult:
    s3 = storage.s3()
    loaded_at = datetime.now(timezone.utc)
    parts = []
    for url, path in landing_paths(source):
        part = read_csv_as_strings(s3, path)
        part = part.append_column("_source_url", pa.array([url] * len(part), pa.string()))
        parts.append(part)
    # files from different months can have different columns; missing ones become null
    data = pa.concat_tables(parts, promote_options="default")
    data = data.append_column("_loaded_at", pa.array([loaded_at] * len(data), pa.timestamp("us", tz="UTC")))

    cat = catalog()
    cat.create_namespace_if_not_exists(NAMESPACE)
    identifier = f"{NAMESPACE}.{source.name}"
    added, missing = [], []
    try:
        table = cat.load_table(identifier)
        existing = set(table.schema().column_names)
        added = [c for c in data.column_names if c not in existing]
        missing = [c for c in table.schema().column_names if c not in data.column_names]
        if added:
            with table.update_schema() as update:
                update.union_by_name(data.schema)
        for column in missing:
            data = data.append_column(column, pa.nulls(len(data), pa.string()))
        table.overwrite(data)
        action = "overwrote"
    except NoSuchTableError:
        table = cat.create_table(identifier, schema=data.schema, properties={"comment": source.description})
        table.append(data)
        action = "created"

    result = LoadResult(len(data), table.current_snapshot().snapshot_id, added, missing)
    print(f"{action} {identifier}: {result.rows:,} rows, snapshot {result.snapshot_id}")
    if added:
        print(f"  schema: added {', '.join(added)}")
    if missing:
        print(f"  schema: no longer in source (left null) {', '.join(missing)}")
    return result
