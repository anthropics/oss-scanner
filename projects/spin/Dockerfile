# Scanner image for https://github.com/spinframework/spin (main): the `spin` CLI and the crates under crates/.
#
# The audit runs offline, so this build fetches every crate the workspace and its example app need, then builds
# the workspace with all targets in the dev profile (debug assertions and overflow checks on): the spin binary,
# every library, every unit, integration and runtime test binary, and the WebAssembly test components and example
# apps that the build scripts compile for the guest targets. threat_model.md, next to this file, says how to run
# all of it.

# Latest stable Rust. The repository's CI pins the version named in Cargo.toml (rust-version) and in
# .github/workflows/build.yml, which is the minimum the code supports; the Makefile uses whatever is installed.
FROM rust:1-trixie
ENV DEBIAN_FRONTEND=noninteractive
# openssl-sys links the system OpenSSL (the release build vendors it instead). clang and cmake build the C in
# libsqlite3-sys and zstd-sys. python3 runs the test harness's helper services (http-echo.py and tcp-echo.py in the
# test-environment crate, which the `services` files under tests/ name); the services that need Docker, and the
# tests that need other language toolchains, sit behind the extern-dependencies-tests cargo feature and are not
# built here.
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang cmake pkg-config libssl-dev python3 \
    && rm -rf /var/lib/apt/lists/*

# Guest targets, as CI installs them: build.rs compiles crates/core/tests/core-wasi-test and
# examples/spin-timer/app-example for wasm32-wasip2, tests/test-components compiles its components for
# wasm32-wasip1, and the integration tests `spin build` Rust template apps.
RUN rustup target add wasm32-wasip1 wasm32-wasip2 wasm32-unknown-unknown

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Every crate in Cargo.lock (registry and git), plus the Rust SDK the example app and the Rust templates depend on,
# and the crates of the custom-trigger example that the test_timer_trigger integration test builds, so that cargo
# never needs the network again (the test components and build-script apps fetch theirs during the build below).
RUN cargo fetch \
    && cargo fetch --manifest-path examples/http-rust/Cargo.toml \
    && cargo fetch --manifest-path examples/spin-timer/Cargo.toml

# Debug info: line tables only (file and line in every backtrace and under gdb, no variable info). With full debug
# info, the 90-odd test binaries of this workspace each weigh 300 MB to 1.2 GB (every crate re-emits debug info for
# the Wasmtime and Tokio generics it instantiates) and the target directory passes 30 GB. Written to CARGO_HOME,
# not the checkout, so git stays clean; threat_model.md says how to get full debug info for one crate.
RUN printf '\n[profile.dev]\ndebug = "line-tables-only"\n' >> "$CARGO_HOME/config.toml"

# Build as CI's "Test Spin" job does before `make test-unit`: the workspace, all targets, default features, in the
# dev profile (debug assertions and overflow checks on). Incremental compilation off, as in CI. A step that fails
# fails the build, and primary_contact gets the log.
ENV CARGO_INCREMENTAL=0
RUN cargo build --workspace --all-targets

# The root package on its own, which is what plain `cargo test` and `cargo test --test integration` select: Cargo
# unifies features per selection, so this is a second set of artifacts for the crates whose features differ.
# Building it here saves an offline rebuild (and a second compile of the test components) later.
RUN cargo test --no-run

# A ready-to-run Spin application: examples/http-rust, built for the wasm32-wasip2 guest target its spin.toml
# names, so `spin up` works there without a build step.
RUN cargo build --manifest-path examples/http-rust/Cargo.toml --target wasm32-wasip2 --release

# One integration test, run online: tests/testcases/assets-test names a component by URL, and spin's loader keeps
# downloads content-addressed under ~/.cache/spin, checking there first. This fills that cache so the test (and any
# `spin up` of that app) works offline. The templates smoke test clones from GitHub every time and cannot be
# cached; threat_model.md lists it.
RUN (timeout 5m cargo test --test integration assets_routing_test \
      || echo "WARNING: assets_routing_test did not pass, so it will not pass offline either")

# The unit tests (`make test-unit`), bounded so a hang cannot stall the build; a failure is reported, not fatal.
RUN (timeout 10m cargo test --workspace --no-fail-fast -- --skip integration_tests --skip runtime_tests \
      || echo "WARNING: unit tests reported failures")

# The host-side artifacts of the test components' wasm builds (build scripts and proc macros compiled for the host,
# about 2 GB per feature variant) are read by nothing afterwards; the components themselves stay in
# target/debug/build/test-components-*/out/wasm32-wasip1/debug/.
RUN rm -rf target/debug/build/test-components-*/out/debug

# The spin binary on PATH (as the Makefile puts it), and every later cargo command (a rebuild after a patch, a test
# run) offline, against what was fetched above.
ENV PATH="/src/target/debug:${PATH}" \
    CARGO_NET_OFFLINE=true
