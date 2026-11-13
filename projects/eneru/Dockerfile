# Eneru: pure-Python (3.9+) UPS monitoring daemon. Built with the repository as context; checkout at /src.
FROM python:3.12-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git openssh-client nut-client \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Runtime extras plus the test tooling (playwright from [dev] is only for the dashboard preview harness; skip it).
RUN pip install -e ".[notifications,auth,mqtt]" \
      "pytest>=7.0.0" "pytest-cov>=4.0.0" "pytest-mock>=3.10.0" "pytest-timeout>=2.1.0" "pytest-xdist>=3.0.0"

# Cheap sanity checks; a failing test must not abort the build.
RUN python -m eneru validate --config examples/config-reference.yaml || echo "WARNING: config validation failed"
RUN (pytest -m unit -q -n auto -p no:cacheprovider || echo "WARNING: unit tests reported failures")
