select
    segmentid as segment_id,
    bikeid as bike_id,
    street,
    fromstreet as from_street,
    tostreet as to_street,
    case boro
        when '1' then 'Manhattan'
        when '2' then 'Bronx'
        when '3' then 'Brooklyn'
        when '4' then 'Queens'
        when '5' then 'Staten Island'
    end as borough,
    status,
    facilitycl as facility_class,
    nullif(ft_facilit, '') as facility_with_traffic,
    nullif(tf_facilit, '') as facility_against_traffic,
    coalesce('Protected' in (ft_facilit, tf_facilit, ft2facilit, tf2facilit), false) as is_protected,
    try_cast(substr(instdate, 1, 10) as date) as installed_on,
    try_cast(substr(ret_date, 1, 10) as date) as retired_on,
    the_geom as geometry_wkt
from {{ source('raw', 'nyc_bike_routes') }}
