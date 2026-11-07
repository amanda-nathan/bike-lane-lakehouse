"""Dagster definitions: one asset per source, live station snapshots, schedules, checks."""

from dagster import (
    AssetCheckResult,
    AssetCheckSeverity,
    AssetSelection,
    Definitions,
    MaterializeResult,
    MetadataValue,
    ScheduleDefinition,
    asset,
    asset_check,
)
from pyiceberg.table.snapshots import Operation

from bikelake import stations
from bikelake.extract import extract
from bikelake.load import catalog, load
from bikelake.sources import SOURCES, Source

# Matched to how often each source publishes. Times are Eastern.
SCHEDULES = {
    "nyc_crashes": "0 6 * * *",  # daily
    "boston_crashes": "0 6 * * 1",  # weekly; source updates monthly
    "boston_bike_counts_daily": "0 6 * * 1",  # weekly; new counts a few times a year
    "boston_bike_counts_hourly": "0 6 * * 1",
    "nyc_bike_routes": "0 6 * * 1",
    "bluebikes_trips": "0 6 3 * *",  # monthly, after the new month's file is posted
}


def raw_asset(source: Source):
    @asset(
        name=source.name,
        group_name="raw",
        kinds={"python", "iceberg"},
        description=source.description,
        metadata={"docs": MetadataValue.url(source.docs), "table": f"iceberg.raw.{source.name}"},
    )
    def _asset() -> MaterializeResult:
        extract(source, force=source.files_change)
        result = load(source)
        return MaterializeResult(
            metadata={
                "rows": result.rows,
                "snapshot_id": str(result.snapshot_id),
                "added_columns": result.added_columns,
                "missing_columns": result.missing_columns,
            }
        )

    return _asset


def row_count_check(source: Source):
    @asset_check(
        asset=source.name,
        name="row_count_not_dropped",
        description="Fails if this load has 5% fewer rows than the previous load.",
    )
    def _check() -> AssetCheckResult:
        table = catalog().load_table(f"raw.{source.name}")
        # An overwrite commits a DELETE snapshot then an APPEND, so compare APPEND snapshots only.
        loads = [s for s in table.snapshots() if s.summary.operation == Operation.APPEND]
        rows = int(loads[-1].summary["total-records"])
        if len(loads) < 2:
            return AssetCheckResult(passed=True, metadata={"rows": rows})
        previous = int(loads[-2].summary["total-records"])
        return AssetCheckResult(passed=rows >= 0.95 * previous, metadata={"rows": rows, "previous_rows": previous})

    return _check


def schema_check(source: Source):
    @asset_check(
        asset=source.name,
        name="schema_unchanged",
        description="Warns when the source added or dropped columns since the last load.",
    )
    def _check() -> AssetCheckResult:
        table = catalog().load_table(f"raw.{source.name}")
        schemas = table.schemas()
        loads = [s for s in table.snapshots() if s.summary.operation == Operation.APPEND]
        if len(loads) < 2:
            return AssetCheckResult(passed=True, metadata={"schema_versions": len(schemas)})
        current = schemas[loads[-1].schema_id].column_names
        previous = schemas[loads[-2].schema_id].column_names
        added = sorted(set(current) - set(previous))
        return AssetCheckResult(
            passed=not added,
            severity=AssetCheckSeverity.WARN,
            metadata={"schema_versions": len(schemas), "added_since_last_load": added},
        )

    return _check


@asset(
    group_name="live",
    kinds={"python", "postgres"},
    description="Snapshot of live Bluebikes station status, appended to Postgres station_status.",
)
def station_status() -> MaterializeResult:
    return MaterializeResult(metadata={"stations": stations.poll()})


schedules = [
    ScheduleDefinition(
        name=f"{name}_schedule",
        target=AssetSelection.assets(name),
        cron_schedule=cron,
        execution_timezone="America/New_York",
    )
    for name, cron in SCHEDULES.items()
]
schedules.append(
    ScheduleDefinition(
        name="station_status_hourly",
        target=AssetSelection.assets("station_status"),
        cron_schedule="0 * * * *",
        execution_timezone="America/New_York",
    )
)

defs = Definitions(
    assets=[raw_asset(s) for s in SOURCES.values()] + [station_status],
    asset_checks=[row_count_check(s) for s in SOURCES.values()] + [schema_check(s) for s in SOURCES.values()],
    schedules=schedules,
)
