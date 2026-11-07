-- Trips per day, start station, member type, and bike type. The 4.6M trips roll up to
-- about 1M rows here, which is the grain the metrics need.
select
    concat(cast(cast(started_at as date) as varchar), '|', coalesce(start_station_id, 'none'), '|', member_type, '|', rideable_type) as trip_day_id,
    cast(started_at as date) as trip_date,
    start_station_id,
    max(start_station_name) as start_station_name,
    member_type,
    rideable_type,
    count(*) as trips,
    count(duration_minutes) as trips_with_duration,
    sum(duration_minutes) as total_duration_minutes
from {{ ref('stg_bluebikes__trips') }}
group by 1, 2, 3, 5, 6
