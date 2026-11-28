# MCP Rust SDK (rmcp), built and tested the way its CI (.github/workflows/ci.yml) does: the tests with all features, and
# again without the "local" feature, which changes the Send bounds of the public API. Some tests start Node.js and
# Python peers, so the image also has Node.js 22 and uv.
FROM rust:1-bookworm

COPY --from=node:22-bookworm /usr/local/bin/ /usr/local/bin/
COPY --from=node:22-bookworm /usr/local/lib/node_modules/ /usr/local/lib/node_modules/
COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /uvx /usr/local/bin/

# Line tables only, and kept out of the many test binaries: backtraces keep file and line, in a far smaller image.
ENV CARGO_INCREMENTAL=0 \
    CARGO_PROFILE_DEV_DEBUG=line-tables-only \
    CARGO_PROFILE_DEV_SPLIT_DEBUGINFO=unpacked \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# An ARG, so that it bounds the memory this build uses without reaching the audit environment.
ARG CARGO_BUILD_JOBS=8

# The toolchain that rust-toolchain.toml names.
RUN rustup toolchain install

# There is no committed Cargo.lock, so this resolves the dependencies once, as CI does.
RUN cargo fetch

# Every rmcp feature but "local" and the internal ones, as in CI. Kept in a file for later use.
RUN cargo metadata --no-deps --format-version 1 | python3 -c 'import json, sys; \
    p = next(p for p in json.load(sys.stdin)["packages"] if p["name"] == "rmcp"); \
    print(",".join(f for f in p["features"] if not f.startswith("__") and f != "local"))' > /opt/rmcp-features

# The tests of both configurations, then the example servers and clients and the conformance server and client, to drive
# the library (not the WASI example). One layer, because the builds replace each other's files.
RUN cargo test --all-features --no-run \
    && cargo test -p rmcp --features "$(cat /opt/rmcp-features)" --no-run \
    && for dir in examples/*/ conformance/; do \
         case "$dir" in *wasi*) continue ;; esac; \
         [ ! -f "$dir/Cargo.toml" ] || cargo build --manifest-path "$dir/Cargo.toml" --all-features --all-targets || exit 1; \
       done

# Run the tests while there is a network: the Node.js and Python peers install their packages on the first run and reuse
# them later. A failing test must not abort the image build.
RUN (timeout 600 cargo test --all-features --no-fail-fast || echo "WARNING: tests with all features reported failures") \
    && (timeout 600 cargo test -p rmcp --features "$(cat /opt/rmcp-features)" --no-fail-fast \
        || echo "WARNING: tests without the local feature reported failures")

# There is no network when the scanner runs, so cargo, npm and uv must use what is installed above.
ENV CARGO_NET_OFFLINE=true \
    UV_OFFLINE=1 \
    npm_config_offline=true
