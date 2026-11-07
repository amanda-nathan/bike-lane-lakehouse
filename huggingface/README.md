# Hugging Face: the dataset and the Bike Lane Explorer

Two free ways to look at the data in a browser, with nothing to install:

| | Link | What it is |
|---|---|---|
| **Dataset** | [AmandaHattaway/bike-lane-lakehouse](https://huggingface.co/datasets/AmandaHattaway/bike-lane-lakehouse) | The mart tables as Parquet files. Pick a table in the viewer, or click **SQL Console** to query it with DuckDB in your browser |
| **Bike Lane Explorer** | [AmandaHattaway/bike-lane-explorer](https://huggingface.co/spaces/AmandaHattaway/bike-lane-explorer) | A web page with two charts and a SQL box. DuckDB runs in your browser ([DuckDB-WASM](https://duckdb.org/docs/api/wasm/overview)) and reads the dataset's files directly, so there's no server |

Neither uses AI. To ask questions in plain English, use the [MCP server](../README.md#use-the-public-server).

## What's left out, and why

- **Bluebikes trips.** The Bluebikes data license doesn't allow publishing the data "as a stand-alone dataset". The MCP server still uses it, since the license allows using the data in a product or service.
- **Boston** data is public domain (Open Data Commons PDDL). **NYC** data has no restrictions on use under the city's Open Data Law (Local Law 11 of 2012), which asks republishers to name the source, the version, and the changes. The dataset card does that.

## Update or rebuild

Needs the local stack running (for the dataset) and `HF_TOKEN` in `.env`, a Hugging Face token with write access.

```bash
uv run --group deploy python huggingface/publish_dataset.py --dry-run   # build into build/hf_dataset, no upload
uv run --group deploy python huggingface/publish_dataset.py             # build and upload the dataset
uv run --group deploy python huggingface/deploy_space.py                # upload the Explorer page
```

`publish_dataset.py` reads the Iceberg tables directly (no Trino), writes one Parquet file per table, and writes the dataset card from the dbt docs, so table and column descriptions match the models. The dataset is a snapshot: it changes when the script is rerun, not with the daily refresh.

To try the Explorer page locally: `python -m http.server -d huggingface/space 8765`, then open http://localhost:8765.

## Why a static page

Hugging Face now runs Docker and Gradio Spaces on its free hardware only for PRO subscribers; static Spaces are free for everyone. That's also why the MCP server runs on Cloud Run instead (the [`space/`](../space/) folder is that earlier Docker attempt). A static page works here because DuckDB can run in the browser and read Parquet files over the web.
