select
    concat(cast(location_id as varchar), '|', cast(count_date as varchar)) as count_day_id,
    location_id,
    location_name,
    count_date,
    count_year,
    season,
    weather,
    bikes,
    vehicles,
    am_peak_bikes,
    pm_peak_bikes,
    cast(bikes as double) / nullif(bikes + vehicles, 0) as bike_share
from {{ ref('stg_boston__bike_counts_daily') }}
