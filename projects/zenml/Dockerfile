# Builds ZenML (https://github.com/zenml-io/zenml) from source for the OSS Scanner.
#
# This mirrors the maintainers' own development install (scripts/install-zenml-dev.sh): ZenML is installed
# editable from /src with the server, database, secrets-store, service-connector and test extras. The
# third-party libraries behind src/zenml/integrations/* are not installed; threat_model.md explains why they
# are lower priority.
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    UV_HTTP_TIMEOUT=600 \
    UV_LINK_MODE=copy \
    ZENML_DEBUG=1 \
    ZENML_ANALYTICS_OPT_IN=false \
    ZENML_ENABLE_RICH_TRACEBACK=false \
    AUTO_OPEN_DASHBOARD=false

# The scanner's own layer adds git, compilers and debuggers on top of this image, so only uv is needed here.
RUN pip install --no-cache-dir uv

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN bash scripts/install-zenml-dev.sh --system \
    && uv pip install --system "setuptools<82" \
    && zenml version \
    && python -c "import zenml.zen_server.zen_server_api"

# Run the server and store unit tests once so the image is known to work offline, but never fail the build on
# a test failure. `zenml login --local --blocking` (or uvicorn zenml.zen_server.zen_server_api:app) starts a
# local server backed by SQLite with no network access.
RUN (timeout 1800 pytest tests/unit/zen_server tests/unit/zen_stores -q -p no:randomly --reruns 0 \
      || echo "WARNING: unit tests reported failures")
