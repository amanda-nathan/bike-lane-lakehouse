with hours as (
    select
        try_cast(count_id as integer) as location_id,
        location_name,
        {{ parse_btd_time('time') }} as count_hour,
        season,
        direction,
        try_cast(bike as integer) as bikes,
        try_cast(car_lgv as integer) as cars,
        try_cast(bus as integer) as buses,
        try_cast(su_truck as integer) + try_cast(mu_truck as integer) as trucks,
        try_cast(motorcycle as integer) as motorcycles,
        try_cast(mv_total as integer) as vehicles
    from {{ source('raw', 'boston_bike_counts_hourly') }}
),

-- The source repeats one location-hour-direction row (2019-06-04, location 21). Keep one.
numbered as (
    select *, row_number() over (partition by location_id, count_hour, direction order by bikes desc) as n
    from hours
)

select location_id, location_name, count_hour, season, direction, bikes, cars, buses, trucks, motorcycles, vehicles
from numbered
where n = 1
