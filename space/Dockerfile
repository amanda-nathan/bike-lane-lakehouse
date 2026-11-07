# Public MCP server on a Hugging Face Space: Trino reads the mart tables from Cloudflare R2
# with a read-only key, and the MCP server listens on 7860. deploy.py uploads this with the
# repo files it needs, so paths here are relative to the repo root.
FROM trinodb/trino:476

COPY --from=ghcr.io/astral-sh/uv:0.11.11 /uv /usr/local/bin/uv

USER root
RUN mkdir -p /home/trino/app && chown trino:trino /home/trino/app
USER trino

ENV UV_PYTHON_INSTALL_DIR=/home/trino/.python \
    UV_LINK_MODE=copy \
    PATH="/home/trino/app/.venv/bin:$PATH" \
    TRINO_HOST=localhost
WORKDIR /home/trino/app

COPY --chown=trino:trino pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --python 3.12
COPY --chown=trino:trino src ./src
COPY --chown=trino:trino dbt ./dbt
RUN uv sync --frozen --no-dev && dbt parse --project-dir dbt --profiles-dir dbt --quiet

# Only the read-only R2 catalog. The image's sample catalogs go; "memory" would allow writes.
RUN rm -f /etc/trino/catalog/*.properties
COPY --chown=trino:trino space/trino/iceberg.properties /etc/trino/catalog/iceberg.properties
COPY --chown=trino:trino space/trino/jvm.config /etc/trino/jvm.config
# Single node: talk to itself over loopback. On Cloud Run it otherwise advertises an internal
# IPv6 address it can't reach, and every query times out.
RUN echo "node.internal-address=127.0.0.1" >> /etc/trino/node.properties
COPY --chown=trino:trino space/start.sh ./start.sh

EXPOSE 7860
CMD ["./start.sh"]
