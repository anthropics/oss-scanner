# python-garminconnect installed from source with its test extras, the way CI runs pytest.
FROM python:3.13-bookworm
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Library plus every optional extra the tests and examples import.
RUN pip install --upgrade pip \
    && pip install -e ".[testing,typed,workout,example]"

# Unit tests only (integration tests need a real Garmin account); do not fail the build on test failures.
RUN pytest -q -m "not integration" || echo "WARNING: pytest reported failures"
