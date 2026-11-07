"""Bad queries come back to the model as an error it can act on. Runs against the local stack: docker compose up -d"""

from bikelake.mcp_server import query_metrics, run_sql


def test_unknown_metric_lists_suggestions():
    result = query_metrics(metrics=["count_day"])
    assert "does not exactly match any known metrics" in result["error"]
    assert "boston_count_days" in result["error"]


def test_unknown_dimension_is_explained():
    result = query_metrics(metrics=["bluebikes_trips"], group_by=["metric_time__monthh"])
    assert "group-by-items" in result["error"]


def test_bad_filter_returns_trino_message():
    result = query_metrics(metrics=["bluebikes_trips"], where=["season = 'Summer'"])
    assert "cannot be resolved" in result["error"]
    assert "sql" in result


def test_bad_column_in_run_sql():
    result = run_sql("SELECT no_such_column FROM fct_nyc_crashes")
    assert "cannot be resolved" in result["error"]
