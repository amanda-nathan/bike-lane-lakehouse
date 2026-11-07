select
    segment_id,
    street,
    from_street,
    to_street,
    borough,
    installed_on,
    year(installed_on) as install_year,
    is_current,
    geometry_wkt
from {{ ref('int_nyc__protected_lane_installs') }}
