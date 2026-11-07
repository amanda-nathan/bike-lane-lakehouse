"""The read-only SQL check behind the MCP run_sql tool. No stack needed."""

import pytest

from bikelake.warehouse import MAX_ROWS, QueryRejected, check_sql


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE iceberg.marts.fct_nyc_crashes",
        "INSERT INTO fct_nyc_crashes SELECT * FROM fct_nyc_crashes",
        "DELETE FROM fct_nyc_crashes",
        "SELECT 1; SELECT 2",
        "SELECT * FROM iceberg.raw.nyc_crashes",
        "SELECT * FROM staging.stg_nyc__crashes",
        "SELECT * FROM postgres.public.station_status",
        "SELECT * FROM fct_nyc_crashes JOIN iceberg.raw.nyc_crashes USING (collision_id)",
        "WITH x AS (SELECT * FROM iceberg.raw.nyc_crashes) SELECT * FROM x",
    ],
)
def test_rejects(sql):
    with pytest.raises(QueryRejected):
        check_sql(sql)


def test_allows_marts_and_ctes():
    sql = check_sql("WITH y AS (SELECT crash_year FROM fct_nyc_crashes) SELECT * FROM y ORDER BY crash_year")
    assert sql.endswith(f"ORDER BY crash_year LIMIT {MAX_ROWS}")


def test_caps_large_limits_and_keeps_small_ones():
    assert check_sql("SELECT * FROM marts.fct_nyc_crashes LIMIT 50000").endswith(f"LIMIT {MAX_ROWS}")
    assert check_sql("SELECT * FROM iceberg.marts.fct_nyc_crashes LIMIT 5").endswith("LIMIT 5")
