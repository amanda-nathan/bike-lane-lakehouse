---
title: Bike Lane Explorer
emoji: 🚲
colorFrom: blue
colorTo: gray
sdk: static
app_file: index.html
pinned: false
license: other
short_description: Boston and NYC bike counts and crashes, with SQL
datasets:
  - AmandaHattaway/bike-lane-lakehouse
---

# Bike Lane Explorer

Charts and a SQL box over the [bike-lane-lakehouse dataset](https://huggingface.co/datasets/AmandaHattaway/bike-lane-lakehouse): Boston bike counts and crashes, and NYC crashes and protected bike lanes. Everything runs in your browser with [DuckDB-WASM](https://duckdb.org/docs/api/wasm/overview): the page reads the dataset's Parquet files directly, with no server. Source code: [github.com/amanda-nathan/bike-lane-lakehouse](https://github.com/amanda-nathan/bike-lane-lakehouse/tree/main/huggingface).

Not affiliated with the City of Boston or the City of New York.
