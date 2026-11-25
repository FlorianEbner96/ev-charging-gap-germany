# Two stages.
#
# build:   downloads the data, runs the tests, the pipeline, the model, the ranking and the map.
#          The build fails if a test fails. Needs internet.
# runtime: a slim image with the code and the finished files only (model, ranking table, map, data dates).
#          No raw data, no notebooks, no dev tools. Nothing is trained when the container starts.
#
# Build:  docker build -t ev-gap .
# Run:    docker run --rm -p 8000:8000 ev-gap      then open http://127.0.0.1:8000

FROM ghcr.io/astral-sh/uv:0.13.6 AS uv

# ---------------------------------------------------------------- build stage
FROM python:3.13-slim-bookworm AS build

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=uv /uv /uvx /bin/

# Dependencies first: this layer is only rebuilt when pyproject.toml or uv.lock change.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project

COPY src ./src
RUN uv sync --locked

# The data is downloaded at build time, so the image is built from a fresh clone.
# The register is updated regularly: an image built later contains newer data and slightly different numbers.
RUN uv run --no-sync python -m ev_gap.download

COPY tests ./tests
RUN uv run --no-sync pytest -q \
    && uv run --no-sync python -m ev_gap.pipeline \
    && uv run --no-sync python -m ev_gap.model \
    && uv run --no-sync python -m ev_gap.ranking \
    && uv run --no-sync python -m ev_gap.mapping

# -------------------------------------------------------------- runtime stage
FROM python:3.13-slim-bookworm AS runtime

# UV_NO_CACHE: do not keep uv's download cache in the image (it would nearly double the size of the layer).
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY --from=uv /uv /uvx /bin/

# The same locked versions as in the build stage, so the saved model loads without a version mismatch.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev

# Only the finished files from the build stage.
COPY --from=build /app/models ./models
COPY --from=build /app/data/processed/ranking.csv /app/data/processed/data_info.json ./data/processed/
COPY --from=build /app/reports/gap_map.html ./reports/gap_map.html

# The service only reads files, so it does not need to run as root.
USER 1000:1000
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

CMD ["uvicorn", "ev_gap.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
