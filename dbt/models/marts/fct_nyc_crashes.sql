{{ config(properties={"partitioning": "ARRAY['year(crash_date)']"}) }}

select
    collision_id,
    crash_date,
    crashed_at,
    year(crash_date) as crash_year,
    borough,
    zip_code,
    latitude,
    longitude,
    on_street,
    cross_street,
    persons_injured,
    persons_killed,
    pedestrians_injured,
    pedestrians_killed,
    cyclists_injured,
    cyclists_killed,
    cyclists_injured + cyclists_killed as cyclists_hurt,
    motorists_injured,
    motorists_killed,
    contributing_factor,
    vehicle_type
from {{ ref('stg_nyc__crashes') }}
