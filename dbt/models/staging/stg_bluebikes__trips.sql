-- Trip times are local (Boston) with no offset, unlike the BTD counts.
with trips as (
    select
        ride_id,
        rideable_type,
        member_casual as member_type,
        cast(substr(started_at, 1, 23) as timestamp(6)) as started_at,
        cast(substr(ended_at, 1, 23) as timestamp(6)) as ended_at,
        start_station_id,
        start_station_name,
        end_station_id,
        end_station_name,
        try_cast(start_lat as double) as start_latitude,
        try_cast(start_lng as double) as start_longitude,
        try_cast(end_lat as double) as end_latitude,
        try_cast(end_lng as double) as end_longitude,
        row_number() over (partition by ride_id order by _loaded_at) as n
    from {{ source('raw', 'bluebikes_trips') }}
)

select
    ride_id,
    rideable_type,
    member_type,
    started_at,
    ended_at,
    start_station_id,
    start_station_name,
    end_station_id,
    end_station_name,
    start_latitude,
    start_longitude,
    end_latitude,
    end_longitude,
    -- Trips across the November clock change can end "before" they start. Leave those null.
    case when ended_at >= started_at then cast(date_diff('second', started_at, ended_at) as double) / 60 end as duration_minutes
from trips
where n = 1  -- a few rides appear twice in the same monthly file
