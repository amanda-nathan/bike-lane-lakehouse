-- Both two-year windows must fall inside the crash data, or "before" and "after" aren't comparable.
with bounds as (
    select min(crash_date) as first_day, max(crash_date) as last_day
    from {{ ref('fct_nyc_crashes') }}
)
select segment_id, installed_on
from {{ ref('fct_nyc_new_lane_safety') }}, bounds
where date_add('day', -730, installed_on) < bounds.first_day
   or date_add('day', 730, installed_on) > bounds.last_day
