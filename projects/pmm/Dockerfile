# Build PMM inside its dev server image, the one PMM's CI runs the pmm-managed tests in. It bundles PostgreSQL,
# ClickHouse, VictoriaMetrics, Grafana and nginx under supervisord, so a reproducer can run the whole server offline.
FROM ghcr.io/percona/pmm:3-dev-container
USER root

COPY . /src
WORKDIR /src

# Keep Go modules in the final image for tests without Internet access.
RUN go mod download

# Same release targets as PMM's own builds; binaries land in /src/bin.
RUN make -C managed release && make -C agent release && make -C admin release \
    && make -C qan-api2 release && make -C vmproxy release
# Run this checkout's services instead of the image's, as .devcontainer/Makefile does in CI.
RUN install -m 755 bin/pmm-managed bin/pmm-managed-init bin/pmm-managed-starlark bin/pmm-agent bin/vmproxy /usr/sbin/ \
    && install -m 755 bin/qan-api2 /usr/sbin/percona-qan-api2
# Installs the UI dependencies (kept for offline tests), then builds.
RUN make -C ui build

# Compile and link every Go test binary without running any, so the scanner starts with a warm build cache.
RUN go test -exec true ./... > /dev/null || echo "WARNING: some Go test packages failed to compile"

# Without a network interface pmm-agent cannot detect the node address the entrypoint registers it with.
ENV PMM_AGENT_SETUP_NODE_ADDRESS=127.0.0.1
