"""Publish the mart tables as a public Hugging Face dataset, queryable in the browser with SQL.

Reads the Iceberg tables directly (no Trino), writes one Parquet file per table, writes the
dataset card from the dbt docs, and uploads. Needs the local stack running and HF_TOKEN in .env.

    uv run --group deploy python huggingface/publish_dataset.py --dry-run   # build only, look at build/hf_dataset
    uv run --group deploy python huggingface/publish_dataset.py             # build and upload

Bluebikes tables are left out: the Bluebikes data license doesn't allow publishing the data
"as a stand-alone dataset". Boston's data is public domain (PDDL); NYC's Open Data Law asks
republishers to name the source, the version, and the changes, which the card does.
"""

import argparse
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pyarrow.parquet as pq
from dotenv import load_dotenv

from bikelake import semantic
from bikelake.load import catalog

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")  # HF_TOKEN

REPO = "AmandaHattaway/bike-lane-lakehouse"
GITHUB = "https://github.com/amanda-nathan/bike-lane-lakehouse"

# table -> (source, license, caveats a reader needs before using the numbers)
TABLES = {
    "fct_boston_bike_counts_daily": ("boston_counts", [
        "Each location is counted for about two days at a time, a few times a year. Compare the same season across years: since 2020 the City also counts in winter and spring, which lowers all-season averages.",
    ]),
    "fct_boston_bike_counts_hourly": ("boston_counts", [
        "Same count days as the daily table, by hour and direction.",
    ]),
    "dim_boston_count_locations": ("boston_counts", []),
    "fct_boston_crashes": ("boston_crashes", [
        "Based on EMS (ambulance) dispatches: crashes without an ambulance call are missing.",
    ]),
    "fct_nyc_crashes": ("nyc_crashes", [
        "Police-reported crashes. Many have no borough recorded, so borough totals are undercounts.",
    ]),
    "dim_nyc_protected_lanes": ("nyc_routes", []),
    "fct_nyc_new_lane_safety": ("nyc_crashes", [
        "One row per lane segment. A crash near several adjacent segments is counted once for each, so don't add rows across segments to count crashes: use count(DISTINCT collision_id) on the crash-level data instead. Details: " + GITHUB + "/blob/main/evals/RESULTS.md#the-double-count-in-the-sql",
        "More people ride on a street after it gets a lane, and there's no per-street ridership count, so a rise in injuries near new lanes doesn't show the lanes made streets more dangerous.",
    ]),
}

SOURCES = {
    "boston_counts": ("Boston Transportation Department bike counts (Analyze Boston)",
                      "https://data.boston.gov/dataset/streets-daily-bike-counts",
                      "Public domain: Open Data Commons PDDL (http://www.opendefinition.org/licenses/odc-pddl)"),
    "boston_crashes": ("Boston Vision Zero crash records (Analyze Boston)",
                       "https://data.boston.gov/dataset/vision-zero-crash-records",
                       "Public domain: Open Data Commons PDDL (http://www.opendefinition.org/licenses/odc-pddl)"),
    "nyc_crashes": ("NYPD Motor Vehicle Collisions - Crashes (NYC Open Data)",
                    "https://data.cityofnewyork.us/d/h9gi-nx95",
                    "NYC Open Data Law (Local Law 11 of 2012): no restrictions on use; republishers name the source, version, and changes"),
    "nyc_routes": ("NYC DOT Bicycle Routes (NYC Open Data)",
                   "https://data.cityofnewyork.us/d/mzxg-pwib",
                   "NYC Open Data Law (Local Law 11 of 2012): no restrictions on use; republishers name the source, version, and changes"),
}


def export(out: Path) -> dict[str, int]:
    data = out / "data"
    data.mkdir(parents=True)
    rows = {}
    cat = catalog()
    for name in TABLES:
        table = cat.load_table(f"marts.{name}").scan().to_arrow()
        pq.write_table(table, data / f"{name}.parquet", compression="zstd")
        rows[name] = table.num_rows
        print(f"{name:32} {table.num_rows:>10,} rows")
    return rows


def card(rows: dict[str, int]) -> str:
    docs = {t["table"].removeprefix("iceberg.marts."): t for t in semantic.tables()}
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    configs = "\n".join(f"  - config_name: {n}\n    data_files: data/{n}.parquet" for n in TABLES)
    lines = [
        "---",
        "license: other",
        "license_name: pddl-and-nyc-open-data",
        "pretty_name: Bike Lane Lakehouse (Boston and NYC)",
        "tags: [transportation, cycling, crashes, boston, new-york-city, open-data]",
        "configs:",
        configs,
        "---",
        "",
        "# Bike Lane Lakehouse: Boston and NYC bike counts and crashes",
        "",
        f"Cleaned, tested tables from [bike-lane-lakehouse]({GITHUB}): public data loaded into Apache Iceberg and modeled with dbt. "
        "Each table is a config: pick one in the viewer, or click **SQL Console** to query it in your browser with DuckDB.",
        "",
        "```sql",
        "-- In the fct_boston_bike_counts_daily config: average bikes per summer count day on Washington St in Roslindale",
        "SELECT count_year, count(*) AS count_days, round(avg(bikes), 1) AS avg_bikes_per_day",
        "FROM train",
        "WHERE location_name = 'Washington Street north of Bexley Road' AND season = 'Summer'",
        "GROUP BY 1 ORDER BY 1",
        "```",
        "",
        f"**Version:** exported {stamp} from commit `{commit}` of the repo. The repo refreshes its own copy daily; this dataset is updated when the script is rerun.",
        "",
        "**Changes from the sources:** dbt staging models cast types, rename columns to snake_case, convert Boston count times from UTC to local time, "
        "remove rows duplicated at the source, combine NYC route record versions, and match crashes to lanes within about 50 m. "
        f"The SQL for every change is in [dbt/models]({GITHUB}/tree/main/dbt/models).",
        "",
        "**Not included:** Bluebikes trips. The Bluebikes data license doesn't allow redistributing the data as a stand-alone dataset.",
        "",
        "Not affiliated with or endorsed by the City of Boston, the City of New York, or their agencies.",
        "",
        "## Sources and licenses",
        "",
        "| Source | License |",
        "|---|---|",
    ]
    for title, url, lic in SOURCES.values():
        lines.append(f"| [{title}]({url}) | {lic} |")
    lines += ["", "## Tables", ""]
    for name, (source, caveats) in TABLES.items():
        doc = docs.get(name, {})
        lines += [f"### `{name}`", "", f"{doc.get('description', '')} {rows[name]:,} rows. Source: {SOURCES[source][0]}.", ""]
        for c in caveats:
            lines.append(f"- **Caveat:** {c}")
        if caveats:
            lines.append("")
        lines += ["| Column | Type | Description |", "|---|---|---|"]
        for col in doc.get("columns", []):
            lines.append(f"| `{col['name']}` | {col['type'] or ''} | {' '.join((col['description'] or '').split())} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="build the files but don't upload")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "hf_dataset")
    args = parser.parse_args()

    if args.out.exists():
        shutil.rmtree(args.out)
    rows = export(args.out)
    (args.out / "README.md").write_text(card(rows))
    print(f"Built {args.out}")
    if args.dry_run:
        return

    from huggingface_hub import HfApi

    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(REPO, repo_type="dataset", exist_ok=True)
    api.upload_folder(folder_path=args.out, repo_id=REPO, repo_type="dataset",
                      commit_message="Update tables", delete_patterns=["data/*.parquet"])
    print(f"https://huggingface.co/datasets/{REPO}")


if __name__ == "__main__":
    main()
