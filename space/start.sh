#!/bin/bash
# Start Trino, wait until it can take queries, then run the MCP server in the foreground.
set -euo pipefail

/usr/lib/trino/bin/run-trino &
until curl -sf localhost:8080/v1/info | grep -q '"starting":false'; do sleep 2; done
exec bikelake-mcp --http --host 0.0.0.0 --port 7860
