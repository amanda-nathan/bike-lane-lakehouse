select
    concat(cast(location_id as varchar), '|', cast(count_hour as varchar), '|', direction) as count_hour_id,
    location_id,
    location_name,
    count_hour,
    cast(count_hour as date) as count_date,
    hour(count_hour) as hour_of_day,
    season,
    direction,
    bikes,
    cars,
    buses,
    trucks,
    motorcycles,
    vehicles
from {{ ref('stg_boston__bike_counts_hourly') }}
