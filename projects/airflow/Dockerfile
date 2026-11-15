# Build Apache Airflow for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline, so everything the
# tests need is installed here. Airflow's reference images and CI run on Debian Bookworm, and Python 3.11
# is the project's default (and what its CI helper scripts pin).
FROM python:3.11-slim-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    AIRFLOW_HOME=/tmp/airflow-home

# Build dependencies: the DEV_APT_DEPS list from scripts/docker/install_os_dependencies.sh, which Airflow's
# CI image uses to build every Python dependency that has no wheel (pykerberos needs the Kerberos headers,
# for example), plus the PostgreSQL and MySQL client headers that database drivers build against.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        apt-transport-https apt-utils build-essential ca-certificates curl dirmngr freetds-bin freetds-dev \
        git graphviz graphviz-dev krb5-user lcov ldap-utils libbluetooth-dev libbz2-dev libc6-dev libdb-dev \
        libev-dev libev4 libffi-dev libgdbm-compat-dev libgdbm-dev libgeos-dev libkrb5-dev libldap2-dev \
        libleveldb-dev libleveldb1d liblzma-dev libncurses5-dev libreadline6-dev libsasl2-2 libsasl2-dev \
        libsasl2-modules libsqlite3-dev libssl-dev libxmlsec1 libxmlsec1-dev libzstd-dev locales lsb-release \
        lzma lzma-dev openssh-client openssl pkg-config pkgconf sasl2-bin sqlite3 tdsodbc tk-dev unixodbc \
        unixodbc-dev uuid-dev wget xz-utils zlib1g-dev \
        libpq-dev default-libmysqlclient-dev \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# Use the uv version the repository pins in uv.lock, as Airflow's CI does.
RUN UV_VERSION="$(sed -n '/^name = "uv"$/{n;s/^version = "\(.*\)"$/\1/p;}' uv.lock)" \
    && pip install --no-cache-dir "uv==${UV_VERSION}"

# The whole development environment, installed the way Airflow's CI image does it
# (scripts/docker/install_airflow_when_building_images.sh): every workspace package (airflow-core, the
# Task SDK, every provider, the shared libraries, the test fixtures) from the committed lock file into
# /src/.venv. lxml and xmlsec are built from source so that both use the system libxml2
# (https://bugs.launchpad.net/lxml/+bug/2110068).
RUN uv sync --frozen --all-packages --no-binary-package lxml --no-binary-package xmlsec

# The test fixtures generate generated/provider_dependencies.json on first use, through a uv script that
# needs the network; generate it now so tests start offline.
RUN uv run scripts/ci/prek/update_providers_dependencies.py

# The network is gone after this point, so `uv run` must use the environment built above as it is,
# never try to re-resolve or re-sync it.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH

# Run a fast, database-free slice of the API server tests so the image is known to work; a failing test
# must not abort the build. Further tests: `uv run pytest <path>` or plain `pytest <path>`.
RUN uv run pytest airflow-core/tests/unit/api_fastapi/auth --skip-db-tests -q -p no:cacheprovider \
    || echo "WARNING: pytest reported failures"
