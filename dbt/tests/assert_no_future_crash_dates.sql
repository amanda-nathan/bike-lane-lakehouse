-- Crash dates after today mean a date was parsed wrong.
select collision_id, crash_date
from {{ ref('fct_nyc_crashes') }}
where crash_date > current_date
