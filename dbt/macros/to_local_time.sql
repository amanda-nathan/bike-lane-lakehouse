{# UTC timestamp -> Boston/New York wall-clock time, as a plain timestamp. #}
{% macro utc_to_local(expr) -%}
    cast(with_timezone({{ expr }}, 'UTC') at time zone 'America/New_York' as timestamp(6))
{%- endmacro %}

{# Boston BTD timestamps look like 6/22/2016 4:00:00.000 and are stored in UTC. #}
{% macro parse_btd_time(column) -%}
    {{ utc_to_local("date_parse(" ~ column ~ ", '%c/%e/%Y %k:%i:%s.%f')") }}
{%- endmacro %}
