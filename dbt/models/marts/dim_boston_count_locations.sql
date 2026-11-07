select
    location_id,
    max_by(location_name, count_date) as location_name,
    avg(latitude) as latitude,
    avg(longitude) as longitude,
    min(count_date) as first_count_date,
    max(count_date) as last_count_date,
    cast(count(*) as integer) as count_days
from {{ ref('stg_boston__bike_counts_daily') }}
group by location_id
