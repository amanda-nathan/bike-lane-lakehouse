---
title: Bike Lane Lakehouse
emoji: 🚲
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
short_description: MCP server for Boston and NYC bike, traffic, and crash data
---

# Bike Lane Lakehouse MCP server

Ask an AI client about Boston and New York City bike counts, Bluebikes trips, and crashes. The data are Apache Iceberg tables on Cloudflare R2, queried with Trino through a read-only key.

Connect from Claude Code:

```bash
claude mcp add --transport http bikelake https://amandahattaway-bike-lane-lakehouse.hf.space/mcp
```

Tools: `list_metrics`, `query_metrics` (dbt semantic layer, with caveats), `describe_tables`, and `run_sql` (one SELECT, 30 seconds, 1,000 rows).

The Space sleeps after 48 hours without use; the first request after that takes about a minute.

Source: [github.com/amanda-nathan/bike-lane-lakehouse](https://github.com/amanda-nathan/bike-lane-lakehouse)
