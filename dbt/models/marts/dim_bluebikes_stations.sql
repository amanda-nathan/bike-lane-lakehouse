select
    start_station_id as station_id,
    max_by(start_station_name, started_at) as station_name,
    approx_percentile(start_latitude, 0.5) as latitude,
    approx_percentile(start_longitude, 0.5) as longitude,
    cast(min(started_at) as date) as first_trip_on,
    cast(max(started_at) as date) as last_trip_on,
    count(*) as trips_started
from {{ ref('stg_bluebikes__trips') }}
where start_station_id is not null
group by start_station_id
