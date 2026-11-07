-- Crashes that hurt a cyclist within about 50 m of a protected lane segment, in the two
-- years before and the two years after the lane went in. Only lanes installed 2015 through
-- October 2024 qualify, so both windows fall inside the crash data (July 2012 onward).
--
-- The 0.0005 degree buffer is about 55 m north-south and 42 m east-west at NYC's latitude.
-- A crash near several adjacent segments matches each of them.
with lanes as (
    select
        segment_id,
        installed_on,
        st_buffer(st_geometryfromtext(geometry_wkt), 0.0005) as zone
    from {{ ref('int_nyc__protected_lane_installs') }}
    where installed_on between date '2015-01-01' and date '2024-10-31'
),

crashes as (
    select
        collision_id,
        crash_date,
        cyclists_injured + cyclists_killed as cyclists_hurt,
        st_point(longitude, latitude) as location
    from {{ ref('stg_nyc__crashes') }}
    where cyclists_injured + cyclists_killed > 0
      and latitude is not null
      and longitude is not null
)

select
    lanes.segment_id,
    lanes.installed_on,
    crashes.collision_id,
    crashes.crash_date,
    crashes.cyclists_hurt,
    case when crashes.crash_date < lanes.installed_on then 'before' else 'after' end as period
from lanes
join crashes
    on st_contains(lanes.zone, crashes.location)
where crashes.crash_date between date_add('day', -730, lanes.installed_on) and date_add('day', 730, lanes.installed_on)
  and crashes.crash_date <> lanes.installed_on  -- the install day itself is neither before nor after
