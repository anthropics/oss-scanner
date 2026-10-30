# Polaris (polaris-id): the build for an offline security scan.
#
# The build context is the polaris-id checkout. The network is available while this file builds and is
# removed afterwards, so every dependency a test needs is fetched here. Base images are pinned by digest
# (multi-architecture indexes); Python packages install from the repository's hashed lock files only.
#
# After the build, in the offline shell:
#     polaris-oss-start                                   # PostgreSQL 16 on :5432, Redis on :6399
#     python3 -m polaris_checks.run                       # the invariant checks (no database)
#     python3 -m pytest polaris_checks/test_checks.py -q  # their detection tests
#     ./scripts/polaris-test.sh                           # the database-backed product suites
#     python3 scripts/polaris-ship.py run                 # the whole local gate (long: see threat_model.md)

FROM rustlang/rust:nightly-bookworm-slim@sha256:b01284ea83d5df8485d772f8b02d8aaf8858fbe20a51fd20f51074bae58e01eb AS rust
FROM node:24-bookworm-slim@sha256:a5f4366e834695d5f363b920c104953a535d3a9864d1bdf74566a0ebe01daee5 AS node
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    HOME=/root \
    LC_ALL=C.UTF-8

RUN apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends \
        build-essential cmake ninja-build git curl ca-certificates gnupg \
        libpq-dev libssl-dev pkg-config redis-server \
    && rm -rf /var/lib/apt/lists/*

# PostgreSQL 16, the major version CI runs, from the PostgreSQL project's apt repository. The build stops if
# the signing key's fingerprint is not the one the project publishes.
RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /tmp/pgdg.asc \
    && gpg --show-keys --with-colons /tmp/pgdg.asc | grep -q ':B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8:' \
    && gpg --batch --yes -o /usr/share/keyrings/pgdg.gpg --dearmor /tmp/pgdg.asc \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] https://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends postgresql-16 postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/* /tmp/pgdg.asc

# Rust (the ZK prover, polaris_zk) and Node (the TypeScript SDK), copied from their pinned images.
COPY --from=rust /usr/local/rustup /usr/local/rustup
COPY --from=rust /usr/local/cargo /usr/local/cargo
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/opt/venv/bin:/usr/local/cargo/bin:/usr/lib/postgresql/16/bin:$PATH

# liboqs from its release commit, with the flags liboqs-python's own installer uses, into the path
# liboqs-python loads from. The import check runs with a PYOQS_VERSION that installer refuses, so a missing
# library fails the build instead of being fetched (the same recipe as polaris_web/Dockerfile.prod).
ARG LIBOQS_TAG=0.16.0
ARG LIBOQS_COMMIT=5a1a854b0dc9f2141bdc771c555ee60c37950183
ENV OQS_INSTALL_PATH=/root/_oqs
RUN git clone --depth 1 --branch "$LIBOQS_TAG" https://github.com/open-quantum-safe/liboqs /tmp/liboqs \
    && test "$(git -C /tmp/liboqs rev-parse HEAD)" = "$LIBOQS_COMMIT" \
    && cmake -S /tmp/liboqs -B /tmp/liboqs/build -G Ninja \
        -DBUILD_SHARED_LIBS=ON -DOQS_BUILD_ONLY_LIB=ON \
        -DOQS_ENABLE_SIG_STFL_LMS=ON -DOQS_ENABLE_SIG_STFL_XMSS=ON \
        -DOQS_HAZARDOUS_EXPERIMENTAL_ENABLE_SIG_STFL_KEY_SIG_GEN=ON \
        -DCMAKE_INSTALL_PREFIX=/root/_oqs \
    && cmake --build /tmp/liboqs/build --parallel "$(nproc)" \
    && cmake --build /tmp/liboqs/build --target install \
    && rm -rf /tmp/liboqs

COPY . /src
WORKDIR /src

# Python 3.12: the test set, the custody drivers and liboqs-python, each from its hashed lock file; then the
# browser the accessibility and page tests drive.
RUN python -m venv /opt/venv \
    && pip install --no-cache-dir --require-hashes -r polaris_web/requirements-dev.txt \
    && pip install --no-cache-dir --require-hashes -r polaris_web/requirements-custody.txt \
    && pip install --no-cache-dir --require-hashes -r polaris_web/requirements-pqc.txt \
    && PYOQS_VERSION=refused-no-fetch python -c "import oqs; print('liboqs', oqs.oqs_version())" \
    && python -m playwright install --with-deps chromium

# The ZK prover: rust-toolchain.toml names a dated nightly, which rustup fetches here. The test binaries
# are built too, and the crate registry is cached, so `cargo test --release` runs offline.
RUN cd polaris_zk && cargo build --release && cargo test --release --no-run && cargo fetch
ENV CARGO_NET_OFFLINE=true

# The TypeScript SDK (npm ci also builds its dist/).
RUN npm ci --prefix sdk/typescript

# PostgreSQL: a cluster owned by the postgres user, with a superuser role named polaris, trusting local
# connections (this image is a test harness, never a deployment). polaris_test is loaded the way CI loads
# it: 00_load_all.sql, then every up migration in order.
ENV POLARIS_DB_HOST=localhost \
    POLARIS_DB_USER=polaris \
    POLARIS_DB_NAME=polaris_test \
    PGHOST=localhost \
    PGUSER=polaris \
    POLARIS_PQC_PROFILE=placeholder \
    POLARIS_TEST_PYTHON=/opt/venv/bin/python
RUN install -d -o postgres -g postgres /var/lib/polaris-pg /var/run/postgresql \
    && runuser -u postgres -- /usr/lib/postgresql/16/bin/initdb -D /var/lib/polaris-pg -U polaris \
        --auth=trust -E UTF8 --locale=C.UTF-8 \
    && printf '%s\n' '#!/bin/sh' 'set -e' \
        'runuser -u postgres -- /usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/polaris-pg -l /var/lib/polaris-pg/server.log -o "-c listen_addresses=localhost -p 5432" -w start' \
        'redis-server --daemonize yes --port 6399 --save "" --dir /tmp' \
        'pg_isready -h localhost -U polaris' \
        > /usr/local/bin/polaris-oss-start \
    && chmod 755 /usr/local/bin/polaris-oss-start \
    && polaris-oss-start \
    && createdb polaris_test \
    && cd polaris_sql && psql -v ON_ERROR_STOP=1 -q -d polaris_test -f 00_load_all.sql \
    && for f in $(ls migrations/*.up.sql | LC_ALL=C sort); do psql -v ON_ERROR_STOP=1 -q -d polaris_test -f "$f" || exit 1; done \
    && runuser -u postgres -- /usr/lib/postgresql/16/bin/pg_ctl -D /var/lib/polaris-pg -w stop \
    && (redis-cli -p 6399 shutdown nosave || true)

# tools/check deletes .dockerignore from the checkout before the build; two invariant checks read it, so it is
# restored from the checkout's own history when that history was copied in.
RUN if [ -d .git ]; then git checkout -- .dockerignore; fi

# A smoke run that must not fail the build: the invariant checks need no database.
RUN python -m polaris_checks.run > /tmp/polaris-checks.log 2>&1 \
    || echo "WARNING: polaris_checks reported a failure; see /tmp/polaris-checks.log"
