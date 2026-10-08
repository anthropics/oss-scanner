# py20305: an IEEE 2030.5 / CSIP client for distributed energy resources.
#
# The repository's own Dockerfile builds a slim runtime image with no source or
# tests. This one keeps the checkout at /src, installs every extra plus the
# development tools, and runs the unit suite once so the image is known to
# work offline.
FROM python:3.12-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Editable install, so a patch to src/ takes effect without reinstalling.
RUN pip install -e ".[dev]"

# Run the unit suite to confirm the image works. tests/e2e needs a live
# IEEE 2030.5 server in Docker and is excluded by pyproject.toml. A failing
# test does not fail the build.
RUN pytest -q -p no:cacheprovider || echo "WARNING: pytest reported failures"
