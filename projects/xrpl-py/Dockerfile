# OSS Scanner build for xrpl-py (https://github.com/XRPLF/xrpl-py): the Python SDK for the XRP Ledger.
# Mirrors the repo's CI (.github/workflows/unit_test.yml): Poetry installs the package and dev dependencies.
#
# This file lives next to project.yaml in the oss-scanner repository. The scanner copies it to
# .oss-scanner/Dockerfile in a fresh clone of xrpl-py and builds it with that clone as the build context. The
# network is available only while this file builds, so every dependency must be fetched here.
FROM python:3.11-bookworm
ENV PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

RUN pip install poetry==2.5.1

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Install xrpl-py and its dev dependencies into /src/.venv.
RUN poetry install

# Smoke-test the image; failures are logged, not fatal. Full suite: `poetry run poe test_unit`.
RUN timeout 900 poetry run python -m unittest discover tests/unit \
    || echo "WARNING: unit tests reported failures"
