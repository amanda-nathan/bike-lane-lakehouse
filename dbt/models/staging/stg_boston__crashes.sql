-- The source has no ID, so one is built from the fields that identify a dispatch.
select
    to_hex(md5(to_utf8(concat_ws('|', dispatch_ts, mode_type, coalesce(lat, ''), coalesce(long, ''), coalesce(street, ''))))) as crash_id,
    {{ utc_to_local("cast(substr(dispatch_ts, 1, 19) as timestamp)") }} as dispatched_at,
    case mode_type when 'bike' then 'bike' when 'ped' then 'pedestrian' when 'mv' then 'motor_vehicle' end as mode,
    location_type,
    street,
    xstreet1 as cross_street,
    try_cast(lat as double) as latitude,
    try_cast(long as double) as longitude
from {{ source('raw', 'boston_crashes') }}
