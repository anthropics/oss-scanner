FROM python:3.12-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends git jq \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Editable install with the dev, signing and identity extras so the test suite
# and the enterprise code paths (receipt signing, JWT identity) import cleanly.
RUN pip install --no-cache-dir -e ".[dev,signing,identity]" requests

# Report test failures without failing the build.
RUN python -m pytest tests -q -p no:randomly || echo "WARNING: pytest reported failures"
