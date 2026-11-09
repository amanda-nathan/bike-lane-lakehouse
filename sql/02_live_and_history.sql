-- Live Bluebikes station status (Postgres) next to a year of trip history (Iceberg),
-- in one Trino query. Run `uv run bikelake stations` first to take a snapshot of the feed.

-- Stations near Boston University: bikes and docks right now, and how many trips usually start
-- there at this hour on this day of the week.
WITH now_local AS (
    SELECT current_timestamp AT TIME ZONE 'America/New_York' AS ts
),
live AS (
    SELECT short_name, name, lat, lon, capacity, bikes_available, docks_available
    FROM postgres.public.station_status
    WHERE fetched_at = (SELECT max(fetched_at) FROM postgres.public.station_status)
),
trips AS (
    SELECT start_station_id AS short_name, CAST(substr(started_at, 1, 19) AS timestamp) AS started
    FROM iceberg.raw.bluebikes_trips
),
typical AS (
    SELECT t.short_name, round(count(*) / 52.0, 1) AS usual_departures
    FROM trips t CROSS JOIN now_local n
    WHERE day_of_week(t.started) = day_of_week(n.ts)
      AND hour(t.started) = hour(n.ts)
    GROUP BY 1
)
SELECT
    l.name,
    l.bikes_available,
    l.docks_available,
    coalesce(t.usual_departures, 0) AS usual_departures_this_hour
FROM live l
LEFT JOIN typical t USING (short_name)
WHERE great_circle_distance(l.lat, l.lon, 42.3505, -71.1054) < 0.8  -- km from Marsh Plaza
ORDER BY usual_departures_this_hour DESC
LIMIT 10;
