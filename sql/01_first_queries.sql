-- Run in the Trino shell: docker compose exec trino trino
-- Raw columns are strings (see docs/decisions/0002), so these cast as they go.

SHOW TABLES FROM iceberg.raw;

DESCRIBE iceberg.raw.boston_bike_counts_daily;


-- Washington St near Hyde Park Ave, summer counts only.
-- Since 2020 the City also counts in winter and spring, so mixing seasons
-- makes later years look lower.
SELECT
    year,
    count(*) AS count_days,
    round(avg(CAST(day_bikes AS integer))) AS avg_bikes,
    round(avg(CAST(day_veh AS integer))) AS avg_vehicles
FROM iceberg.raw.boston_bike_counts_daily
WHERE location_name = 'Washington Street north of Bexley Road'
  AND season = 'Summer'
GROUP BY year
ORDER BY year;


-- Busiest hours for bikes across all Boston sites.
-- Times are stored in UTC. Without converting, the peak shows up at 9pm.
SELECT
    hour(with_timezone(date_parse(time, '%c/%e/%Y %k:%i:%s.%f'), 'UTC')
         AT TIME ZONE 'America/New_York') AS hour_of_day,
    sum(CAST(bike AS integer)) AS bikes
FROM iceberg.raw.boston_bike_counts_hourly
GROUP BY 1
ORDER BY bikes DESC
LIMIT 5;


-- NYC protected bike lane segments by install year
SELECT
    year(CAST(substr(instdate, 1, 10) AS date)) AS install_year,
    count(*) AS protected_segments
FROM iceberg.raw.nyc_bike_routes
WHERE 'Protected' IN (ft_facilit, tf_facilit)
  AND instdate IS NOT NULL
GROUP BY 1
ORDER BY 1 DESC
LIMIT 10;


-- NYC cyclists injured and killed by year
SELECT
    year(CAST(substr(crash_date, 1, 10) AS date)) AS crash_year,
    sum(CAST(number_of_cyclist_injured AS integer)) AS cyclists_injured,
    sum(CAST(number_of_cyclist_killed AS integer)) AS cyclists_killed
FROM iceberg.raw.nyc_crashes
GROUP BY 1
ORDER BY 1 DESC
LIMIT 10;


-- Snapshots: one per load. Reload a table and a new row shows up.
SELECT snapshot_id, parent_id, operation, committed_at
FROM iceberg.raw."boston_bike_counts_daily$snapshots"
ORDER BY committed_at;

-- Data files behind a table
SELECT file_path, record_count, file_size_in_bytes
FROM iceberg.raw."nyc_crashes$files";

-- Time travel: read the table as of an earlier snapshot
-- SELECT count(*) FROM iceberg.raw.boston_bike_counts_daily FOR VERSION AS OF <snapshot_id>;


-- Partitioning: copy NYC crashes into a typed table partitioned by year.
-- Queries just filter on crash_date; Iceberg uses the partitions to skip files.
CREATE SCHEMA IF NOT EXISTS iceberg.sandbox;

CREATE TABLE IF NOT EXISTS iceberg.sandbox.nyc_crashes
WITH (partitioning = ARRAY['year(crash_date)'])
AS
SELECT
    collision_id,  -- hex string, not a number
    CAST(substr(crash_date, 1, 10) AS date) AS crash_date,
    borough,
    TRY_CAST(latitude AS double) AS latitude,
    TRY_CAST(longitude AS double) AS longitude,
    CAST(number_of_cyclist_injured AS integer) AS cyclists_injured,
    CAST(number_of_cyclist_killed AS integer) AS cyclists_killed
FROM iceberg.raw.nyc_crashes;

-- Compare the input rows and bytes read in each plan
EXPLAIN ANALYZE
SELECT count(*) FROM iceberg.raw.nyc_crashes
WHERE substr(crash_date, 1, 4) = '2025';

EXPLAIN ANALYZE
SELECT count(*) FROM iceberg.sandbox.nyc_crashes
WHERE crash_date >= DATE '2025-01-01' AND crash_date < DATE '2026-01-01';
