-- One row per protected lane segment installed 2015 through October 2024: cyclist-injury
-- crashes within about 50 m in the two years before and after, next to citywide cyclist
-- injuries over the same two windows. Comparing the two changes accounts for citywide
-- trends; it does not account for more people riding on a street once it has a lane.
with lanes as (
    select *
    from {{ ref('int_nyc__protected_lane_installs') }}
    where installed_on between date '2015-01-01' and date '2024-10-31'
),

nearby as (
    select
        segment_id,
        count_if(period = 'before') as crashes_before,
        count_if(period = 'after') as crashes_after,
        sum(case when period = 'before' then cyclists_hurt else 0 end) as hurt_before,
        sum(case when period = 'after' then cyclists_hurt else 0 end) as hurt_after
    from {{ ref('int_nyc__cyclist_crashes_near_new_lanes') }}
    group by segment_id
),

citywide_daily as (
    select crash_date, sum(cyclists_injured + cyclists_killed) as hurt
    from {{ ref('stg_nyc__crashes') }}
    group by crash_date
),

citywide as (
    select
        lanes.segment_id,
        sum(case when citywide_daily.crash_date < lanes.installed_on then citywide_daily.hurt else 0 end) as hurt_before,
        sum(case when citywide_daily.crash_date > lanes.installed_on then citywide_daily.hurt else 0 end) as hurt_after
    from lanes
    join citywide_daily
        on citywide_daily.crash_date between date_add('day', -730, lanes.installed_on) and date_add('day', 730, lanes.installed_on)
    group by lanes.segment_id
)

select
    lanes.segment_id,
    lanes.street,
    lanes.from_street,
    lanes.to_street,
    lanes.borough,
    lanes.installed_on,
    year(lanes.installed_on) as install_year,
    coalesce(nearby.crashes_before, 0) as cyclist_crashes_before,
    coalesce(nearby.crashes_after, 0) as cyclist_crashes_after,
    coalesce(nearby.hurt_before, 0) as cyclists_hurt_before,
    coalesce(nearby.hurt_after, 0) as cyclists_hurt_after,
    citywide.hurt_before as citywide_cyclists_hurt_before,
    citywide.hurt_after as citywide_cyclists_hurt_after
from lanes
left join nearby on nearby.segment_id = lanes.segment_id
left join citywide on citywide.segment_id = lanes.segment_id
