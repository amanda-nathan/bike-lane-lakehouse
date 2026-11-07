"""Poll the live Bluebikes station feed (GBFS) into Postgres."""

import time
from datetime import datetime, timezone

import psycopg
import requests

from bikelake.config import POSTGRES_DSN

GBFS = "https://gbfs.lyft.com/gbfs/1.1/bos/en"

DDL = """
CREATE TABLE IF NOT EXISTS station_status (
    fetched_at        timestamptz NOT NULL,
    station_id        text NOT NULL,
    short_name        text,
    name              text,
    lat               double precision,
    lon               double precision,
    capacity          integer,
    bikes_available   integer,
    ebikes_available  integer,
    docks_available   integer,
    is_renting        boolean,
    last_reported     timestamptz,
    PRIMARY KEY (station_id, fetched_at)
)
"""

INSERT = """
INSERT INTO station_status VALUES (
    %(fetched_at)s, %(station_id)s, %(short_name)s, %(name)s, %(lat)s, %(lon)s, %(capacity)s,
    %(bikes_available)s, %(ebikes_available)s, %(docks_available)s, %(is_renting)s, %(last_reported)s
)
"""


def fetch() -> list[dict]:
    info = requests.get(f"{GBFS}/station_information.json", timeout=30).json()["data"]["stations"]
    status = requests.get(f"{GBFS}/station_status.json", timeout=30).json()["data"]["stations"]
    info_by_id = {s["station_id"]: s for s in info}
    fetched_at = datetime.now(timezone.utc)

    rows = []
    for s in status:
        i = info_by_id.get(s["station_id"], {})
        rows.append(
            {
                "fetched_at": fetched_at,
                "station_id": s["station_id"],
                "short_name": i.get("short_name"),
                "name": i.get("name"),
                "lat": i.get("lat"),
                "lon": i.get("lon"),
                "capacity": i.get("capacity"),
                "bikes_available": s.get("num_bikes_available"),
                "ebikes_available": s.get("num_ebikes_available"),
                "docks_available": s.get("num_docks_available"),
                "is_renting": bool(s.get("is_renting")),
                "last_reported": datetime.fromtimestamp(s["last_reported"], timezone.utc),
            }
        )
    return rows


def poll(every: int | None = None) -> int:
    """Insert one snapshot, or keep polling every N seconds. Returns rows in the last snapshot."""
    with psycopg.connect(POSTGRES_DSN, autocommit=True) as conn:
        conn.execute(DDL)
        while True:
            rows = fetch()
            with conn.cursor() as cur:
                cur.executemany(INSERT, rows)
            print(f"{rows[0]['fetched_at']:%Y-%m-%d %H:%M:%S} inserted {len(rows)} station rows")
            if every is None:
                return len(rows)
            time.sleep(every)
