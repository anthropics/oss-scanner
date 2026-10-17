# Home Assistant custom component with its pytest harness, mirroring .github/workflows/tests.yaml.
# Home Assistant >= 2026.3 needs Python >= 3.14.
FROM python:3.14-bookworm
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential libffi-dev libssl-dev libjpeg-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Home Assistant core, ha-garmin and the test tooling (pytest-homeassistant-custom-component).
RUN pip install --upgrade pip \
    && pip install -r requirements.txt -r requirements_lint.txt

# Run the test suite so you know the image works; do not fail the build on test failures.
RUN pytest tests/ -q || echo "WARNING: pytest reported failures"
