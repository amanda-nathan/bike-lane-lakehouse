select
    collision_id,
    cast(substr(crash_date, 1, 10) as date) as crash_date,
    try_cast(date_parse(substr(crash_date, 1, 10) || ' ' || crash_time, '%Y-%m-%d %k:%i') as timestamp(6)) as crashed_at,
    case borough
        when 'MANHATTAN' then 'Manhattan'
        when 'BRONX' then 'Bronx'
        when 'BROOKLYN' then 'Brooklyn'
        when 'QUEENS' then 'Queens'
        when 'STATEN ISLAND' then 'Staten Island'
    end as borough,
    nullif(zip_code, '') as zip_code,
    -- 0,0 means no location was recorded
    nullif(try_cast(latitude as double), 0) as latitude,
    nullif(try_cast(longitude as double), 0) as longitude,
    nullif(trim(on_street_name), '') as on_street,
    nullif(trim(coalesce(nullif(cross_street_name, ''), off_street_name)), '') as cross_street,
    coalesce(try_cast(number_of_persons_injured as integer), 0) as persons_injured,
    coalesce(try_cast(number_of_persons_killed as integer), 0) as persons_killed,
    coalesce(try_cast(number_of_pedestrians_injured as integer), 0) as pedestrians_injured,
    coalesce(try_cast(number_of_pedestrians_killed as integer), 0) as pedestrians_killed,
    coalesce(try_cast(number_of_cyclist_injured as integer), 0) as cyclists_injured,
    coalesce(try_cast(number_of_cyclist_killed as integer), 0) as cyclists_killed,
    coalesce(try_cast(number_of_motorist_injured as integer), 0) as motorists_injured,
    coalesce(try_cast(number_of_motorist_killed as integer), 0) as motorists_killed,
    nullif(contributing_factor_vehicle_1, '') as contributing_factor,
    nullif(vehicle_type_code1, '') as vehicle_type
from {{ source('raw', 'nyc_crashes') }}
