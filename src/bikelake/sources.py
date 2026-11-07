"""Datasets loaded by bikelake."""

import re
from collections.abc import Callable
from dataclasses import dataclass

import requests


@dataclass(frozen=True)
class Source:
    name: str  # table name in iceberg.raw
    city: str
    docs: str
    description: str
    urls: tuple[str, ...] = ()
    find_urls: Callable[[], tuple[str, ...]] | None = None  # for sources that add files over time
    files_change: bool = True  # False when a published file never changes (monthly trip files)

    def resolve_urls(self) -> tuple[str, ...]:
        return self.find_urls() if self.find_urls else self.urls


NYC_SODA = "https://data.cityofnewyork.us/resource"
BLUEBIKES_S3 = "https://s3.amazonaws.com/hubway-data"



def bluebikes_last_12_months() -> tuple[str, ...]:
    # File names aren't consistent (.zip, .csv.zip, .csv), so match on the month prefix.
    listing = requests.get(f"{BLUEBIKES_S3}/", timeout=60).text
    keys = re.findall(r"<Key>(\d{6}-bluebikes-tripdata[^<]*)</Key>", listing)
    return tuple(f"{BLUEBIKES_S3}/{k}" for k in sorted(keys)[-12:])

SOURCES = {
    s.name: s
    for s in [
        Source(
            name="boston_bike_counts_daily",
            city="boston",
            urls=(
                "https://data.boston.gov/dataset/9344a630-7a6d-4554-b741-915c78a26d19/resource/"
                "9c3c421e-5764-4d8d-8a6c-a4d5fa4a67c9/download/streets_daily_bike_counts.csv",
            ),
            docs="https://data.boston.gov/dataset/streets-daily-bike-counts",
            description="BTD automated counts: one row per location per day, ~90 locations, 2016-present.",
        ),
        Source(
            name="boston_bike_counts_hourly",
            city="boston",
            urls=(
                "https://data.boston.gov/dataset/51e791d3-7e44-4848-94aa-597d37c61b6b/resource/"
                "c97f6d9a-aee1-4f95-aea1-a47b74608506/download/streets_hourly_bike_counts.csv",
            ),
            docs="https://data.boston.gov/dataset/streets-hourly-bike-counts",
            description="Same program, one row per location per direction per hour, bikes + vehicle classes.",
        ),
        Source(
            name="boston_crashes",
            city="boston",
            urls=(
                "https://data.boston.gov/dataset/7b29c1b2-7ec2-4023-8292-c24f5d8f0905/resource/"
                "e4bfe397-6bfc-49c5-9367-c879fac7401d/download/tmp6uic_r9e.csv",
            ),
            docs="https://data.boston.gov/dataset/vision-zero-crash-records",
            description="Vision Zero crash records (EMS dispatch based), 2015-present.",
        ),
        Source(
            name="bluebikes_trips",
            city="boston",
            find_urls=bluebikes_last_12_months,
            files_change=False,
            docs="https://bluebikes.com/system-data",
            description="Bluebikes trip history, one row per trip, last 12 months.",
        ),
        Source(
            name="nyc_bike_routes",
            city="nyc",
            urls=(f"{NYC_SODA}/mzxg-pwib.csv?$limit=1000000",),
            docs="https://data.cityofnewyork.us/d/mzxg-pwib",
            description="Bike network segments with install date (instdate) and facility class.",
        ),
        Source(
            name="nyc_crashes",
            city="nyc",
            urls=(f"{NYC_SODA}/h9gi-nx95.csv?$limit=10000000&$order=collision_id",),
            docs="https://data.cityofnewyork.us/d/h9gi-nx95",
            description="NYPD motor vehicle collisions, 2012-present, ~2.3M rows.",
        ),
    ]
}
