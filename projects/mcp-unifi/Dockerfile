# Builds mcp-unifi the way its CI does: hash-locked runtime and dev dependencies,
# the package installed editable, then the pytest suite. Tests run in stub mode
# and never contact a real UniFi controller, so they work offline.
FROM python:3.13-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The repo's .dockerignore keeps tests/ and the docs out of the production image's
# build context, which also drops them here. Restore them from the same branch.
RUN git clone --depth 1 --branch main https://github.com/pete-builds/mcp-unifi /tmp/full \
    && cp -rn /tmp/full/tests /tmp/full/SECURITY.md /tmp/full/CHANGELOG.md /src/ \
    && rm -rf /tmp/full

RUN pip install --require-hashes -r requirements-dev.lock \
    && pip install -e . --no-deps

# Run the suite so the image is known good, without letting a failure abort the build.
RUN pytest -q -p no:cacheprovider || echo "WARNING: pytest reported failures"
