select count_day_id, bike_share
from {{ ref('fct_boston_bike_counts_daily') }}
where bike_share < 0 or bike_share > 1
