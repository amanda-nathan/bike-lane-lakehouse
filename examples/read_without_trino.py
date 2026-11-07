"""Read an Iceberg table with PyIceberg + DuckDB, without Trino.

Same table, same files, different engine. This is how a Python model or notebook
would use the lakehouse.

    uv run python examples/read_without_trino.py
"""

from bikelake.load import catalog

trips = catalog().load_table("raw.bluebikes_trips")

# Only the needed columns are read from the Parquet files.
con = trips.scan(selected_fields=("started_at", "member_casual", "rideable_type")).to_duckdb("trips")

print(
    con.sql(
        """
        SELECT
            substr(started_at, 1, 7) AS month,
            count(*) AS trips,
            round(100.0 * count_if(rideable_type = 'electric_bike') / count(*), 1) AS pct_ebike,
            round(100.0 * count_if(member_casual = 'member') / count(*), 1) AS pct_member
        FROM trips
        GROUP BY 1
        ORDER BY 1
        """
    )
)
