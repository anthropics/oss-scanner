# py1815: a DNP3 (IEEE 1815) outstation and master in pure Python.
#
# The repository's own Dockerfile builds a slim runtime image with no source or
# tests. This one keeps the checkout at /src, installs the development extras,
# and runs the test suite once so the image is known to work offline.
FROM python:3.12-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# Chromium runs the web console tests in tests/browser.py. Without a browser
# those tests skip.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git chromium \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Editable install, so a patch to src/ takes effect without reinstalling.
RUN pip install -e ".[dev]"

# Run the suite to confirm the image works. A failing test does not fail the build.
RUN pytest -q -p no:cacheprovider || echo "WARNING: pytest reported failures"
