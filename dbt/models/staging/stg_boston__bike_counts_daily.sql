select
    try_cast(count_id as integer) as location_id,
    location_name,
    cast({{ parse_btd_time('date') }} as date) as count_date,
    season,
    try_cast(year as integer) as count_year,
    weather,
    try_cast(lat as double) as latitude,
    try_cast(long as double) as longitude,
    try_cast(day_bikes as integer) as bikes,
    try_cast(day_veh as integer) as vehicles,
    try_cast(am_bike as integer) as am_peak_bikes,
    try_cast(pm_bike as integer) as pm_peak_bikes
from {{ source('raw', 'boston_bike_counts_daily') }}
