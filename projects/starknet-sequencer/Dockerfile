# Scanner image for https://github.com/starkware-libs/sequencer (main-v0.14.4): the Apollo sequencer node, the
# blockifier and the Sierra-to-CASM / Sierra-to-native compilers it drives.
#
# The repository's own base image (deployments/images/base/Dockerfile) compiles a dozen cargo tools from source and
# does not fit the scanner's build time, so this installs only what building and testing needs: LLVM 19 + MLIR from
# the repository's script, the toolchain in rust-toolchain.toml, a prebuilt cargo-nextest, and the pinned
# starknet-sierra-compile binary that apollo_compile_to_casm runs. The audit runs offline, so the build then fetches
# every crate and the starknet-specs checkout the RPC spec tests read, and compiles the node and the test binaries of
# the crates threat_model.md, next to this file, points at.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive \
    TZ=Etc/UTC
# A stalled download (apt.llvm.org's MLIR packages are large) times out and retries instead of using up the build time.
RUN printf '%s\n' 'Acquire::Retries "5";' 'Acquire::http::Timeout "60";' 'Acquire::https::Timeout "60";' \
      > /etc/apt/apt.conf.d/80-retries
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang curl git gnupg jq libssl-dev libzstd-dev lsb-release pkg-config \
      protobuf-compiler python3-dev python3-venv software-properties-common tzdata unzip wget zstd \
    && rm -rf /var/lib/apt/lists/*

# The same layout as the repository's base image.
ENV RUSTUP_HOME=/var/tmp/rust \
    CARGO_HOME=/var/tmp/rust
ENV PATH=${CARGO_HOME}/bin:$PATH \
    CARGO_TOOLS_ROOT=${CARGO_HOME}/tools \
    LLVM_SYS_191_PREFIX=/usr/lib/llvm-19/ \
    MLIR_SYS_190_PREFIX=/usr/lib/llvm-19/ \
    TABLEGEN_190_PREFIX=/usr/lib/llvm-19/

# cargo-nextest, at the version scripts/install_cargo_tools.sh pins; CI's run_tests.py runs tests with it.
ARG NEXTEST_VERSION=0.9.113
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain none \
    && curl -fsSL "https://get.nexte.st/${NEXTEST_VERSION}/linux" | tar -xzf - -C "${CARGO_HOME}/bin"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# LLVM 19 with MLIR and Polly (cairo-native links them), then the toolchain rust-toolchain.toml pins.
RUN scripts/install_llvm19.sh \
    && rustup toolchain install \
    && cargo --version && cargo nextest --version

# .cargo/config.toml routes rustc through sccache, which this image leaves out.
ENV RUSTC_WRAPPER= \
    CARGO_BUILD_RUSTC_WRAPPER=

# The starknet-sierra-compile binary apollo_compile_to_casm runs, at the version the repository pins, where it looks
# for it ($CARGO_TOOLS_ROOT).
RUN scripts/install_compiler_binaries.sh --sierra

ENV VIRTUAL_ENV=/opt/sequencer_venv
RUN python3 -m venv ${VIRTUAL_ENV} && ${VIRTUAL_ENV}/bin/pip install -r scripts/requirements.txt
ENV PATH=${VIRTUAL_ENV}/bin:$PATH

# The starknet-specs revision the RPC spec tests check against (scripts/prepare_starknet_specs.sh, which needs a .git
# directory the build context may not have).
ENV STARKNET_SPECS_DIR=/opt/starknet-specs
RUN rev="$(tr -d '[:space:]' < crates/starknet_transaction_prover/resources/starknet_specs_rev.txt)" \
    && git clone --filter=blob:none --sparse https://github.com/starkware-libs/starknet-specs.git \
         "${STARKNET_SPECS_DIR}" \
    && git -C "${STARKNET_SPECS_DIR}" checkout "${rev}" \
    && git -C "${STARKNET_SPECS_DIR}" sparse-checkout set api proving-api

# The Cairo 1 compiler releases blockifier's tests download on first use (blockifier_test_utils/src/cairo_compile.rs):
# 2.1.0 and 2.7.0 for the legacy test contracts, and the version the repository pins. Same layout and completion
# marker.
RUN for v in 2.1.0 2.7.0 "$(tr -d '[:space:]' < crates/apollo_infra_utils/src/cairo_compiler_version.txt)"; do \
      dir="target/bin/cairo_package__${v}" && mkdir -p "${dir}" \
      && curl -fsSL \
         "https://github.com/starkware-libs/cairo/releases/download/v${v}/release-x86_64-unknown-linux-musl.tar.gz" \
         | tar -xz -C "${dir}" \
      && test -x "${dir}/cairo/bin/starknet-compile" && test -x "${dir}/cairo/bin/starknet-sierra-compile" \
      && touch "${dir}/.download_complete" || exit 1; \
    done

# Line-table debug info for the workspace's own crates keeps the target directory a manageable size; CI's tests use the
# dev profile, as here. RUST_BACKTRACE stays unset: apollo_compile_to_casm's tests compare the compiler's stderr,
# which a backtrace note breaks.
ENV CARGO_TERM_COLOR=never \
    SEED=0 \
    CARGO_PROFILE_DEV_DEBUG=line-tables-only \
    CARGO_PROFILE_TEST_DEBUG=line-tables-only

# No debug info for third-party crates: it cuts the image by about a third, and exporting the image counts against the
# build time. This sits in $CARGO_HOME/config.toml, so later cargo runs see it too and reuse what is built here.
RUN printf '%s\n' '[profile.dev.package."*"]' 'debug = false' >> "${CARGO_HOME}/config.toml"

# Every crate in Cargo.lock, for every target and feature, so building any other crate or feature later stays offline.
RUN cargo fetch --locked

# The node binary, and the test binaries of the crates that handle untrusted input (default features, as CI's
# run_tests.py builds them). Other crates' tests compile offline from the fetched crates. A step that fails fails the
# build, and primary_contact gets the log.
ENV SCAN_PACKAGES="-p starknet_api -p blockifier -p apollo_gateway -p apollo_http_server -p apollo_mempool \
-p apollo_batcher -p apollo_class_manager -p apollo_compile_to_casm -p apollo_compile_to_native -p apollo_consensus \
-p apollo_consensus_orchestrator -p apollo_network -p apollo_protobuf -p apollo_p2p_sync -p apollo_rpc \
-p apollo_storage -p starknet_committer -p starknet_patricia"
RUN cargo build --locked --bin apollo_node \
    && cargo nextest run --locked --no-run ${SCAN_PACKAGES}

# Run a few fast, self-contained crates' tests so the log shows the image works, without letting a failure (or a test
# that needs the Internet or CI credentials) abort the build. Same package set as above, so nothing is rebuilt.
RUN timeout 600 cargo nextest run --locked ${SCAN_PACKAGES} --no-fail-fast \
      -E 'package(starknet_api) | package(blockifier) | package(apollo_gateway) | package(apollo_mempool) \
         | package(apollo_compile_to_casm)' \
    || echo "WARNING: cargo nextest reported failures"

# Everything is fetched. From here on cargo must not try to reach a registry.
ENV CARGO_NET_OFFLINE=true
