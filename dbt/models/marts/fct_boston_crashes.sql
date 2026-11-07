select
    crash_id,
    dispatched_at,
    cast(dispatched_at as date) as crash_date,
    mode,
    location_type,
    street,
    cross_street,
    latitude,
    longitude
from {{ ref('stg_boston__crashes') }}
