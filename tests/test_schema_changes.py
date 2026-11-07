"""Schema changes in a source. Runs against the local stack: docker compose up -d"""

import pytest

from bikelake import storage
from bikelake.config import LANDING_BUCKET
from bikelake.load import NAMESPACE, catalog, load
from bikelake.sources import Source

SOURCE = Source(
    name="test_schema_changes",
    city="test",
    docs="",
    description="test table",
    urls=("https://example.com/test.csv",),
)
LANDING_PATH = f"{LANDING_BUCKET}/{SOURCE.name}/{SOURCE.name}.csv"
TABLE = f"{NAMESPACE}.{SOURCE.name}"


def land(csv_text: str) -> None:
    with storage.s3().open_output_stream(LANDING_PATH) as f:
        f.write(csv_text.encode())


@pytest.fixture(autouse=True)
def fresh_table():
    cat = catalog()
    if cat.table_exists(TABLE):
        cat.purge_table(TABLE)
    yield
    cat.purge_table(TABLE)  # drop_table would leave the files in storage
    storage.s3().delete_dir(f"{LANDING_BUCKET}/{SOURCE.name}")


def test_new_column_is_added_and_old_snapshot_still_reads():
    land("id,name\n1,a\n2,b\n")
    first = load(SOURCE)

    land("id,name,lanes\n3,c,2\n")
    second = load(SOURCE)

    assert second.added_columns == ["lanes"]
    table = catalog().load_table(TABLE)
    assert "lanes" in table.schema().column_names
    assert table.scan().to_arrow().column("lanes").to_pylist() == ["2"]
    assert table.scan(snapshot_id=first.snapshot_id).to_arrow().num_rows == 2


def test_dropped_column_is_kept_as_null():
    land("id,name,lanes\n1,a,2\n")
    load(SOURCE)

    land("id,name\n2,b\n")
    result = load(SOURCE)

    assert result.missing_columns == ["lanes"]
    rows = catalog().load_table(TABLE).scan().to_arrow().to_pylist()
    assert rows[0]["id"] == "2"
    assert rows[0]["lanes"] is None
