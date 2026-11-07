-- One row per street segment that has ever had a protected bike lane, with the date the
-- first one went in. Route rows are versioned (Current and Retired), so a segment can
-- appear several times in staging.
select
    segment_id,
    min(installed_on) as installed_on,
    min_by(street, installed_on) as street,
    min_by(from_street, installed_on) as from_street,
    min_by(to_street, installed_on) as to_street,
    min_by(borough, installed_on) as borough,
    bool_or(status = 'Current') as is_current,
    min_by(geometry_wkt, installed_on) as geometry_wkt
from {{ ref('stg_nyc__bike_routes') }}
where is_protected
  and installed_on is not null
group by segment_id
