FROM python:3.12-slim AS app
COPY --from=ghcr.io/astral-sh/uv:0.11.11 /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    DAGSTER_HOME=/dagster_home
RUN mkdir -p /dagster_home

CMD ["dagster", "dev", "-h", "0.0.0.0", "-p", "3000", "-m", "bikelake.defs"]


FROM app AS notebook
RUN uv sync --frozen --no-dev --group notebook
WORKDIR /app/notebooks
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--IdentityProvider.token=", "--ServerApp.password="]
