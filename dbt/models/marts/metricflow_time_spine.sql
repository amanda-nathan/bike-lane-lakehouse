-- One row per day. MetricFlow uses it for time grains and cumulative metrics.
select date_day
from unnest(sequence(date '2010-01-01', date '2030-12-31', interval '1' day)) as t(date_day)
