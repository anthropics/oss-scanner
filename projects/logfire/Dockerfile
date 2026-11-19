# The scanner uses the repository root as the build context and audits /src offline, so everything the
# tests need is installed here, from the committed uv.lock, as CI does.
FROM ghcr.io/astral-sh/uv:python3.13-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY . /src
WORKDIR /src

RUN uv sync --frozen 

# The network is gone after this point, so `uv run` must use the environment above as it is.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH

# Run the test suite so the image is known to work; a failing test must not abort the build. The three
# ignored files start Redis and MySQL containers with testcontainers, and there is no Docker daemon here.
RUN pytest -n logical --dist=loadgroup -q -p no:cacheprovider \
      --ignore=tests/otel_integrations/test_celery.py \
      --ignore=tests/otel_integrations/test_mysql.py \
      --ignore=tests/otel_integrations/test_redis.py \
    || echo "WARNING: pytest reported failures"
