# OSS Scanner build of chia-blockchain.
#
# The scanner builds this with the chia-blockchain checkout as the build context, so `COPY . /src` puts it at /src.
# Network access exists only while this file builds; the scan runs offline, so everything the agent might need is
# fetched here.
#
# What is built:
#   /src/.venv           chia-blockchain installed editable with dev extras, as `./install.sh -d` does for developers.
#   /deps/chia_rs        chia_rs source at the exact version chia-blockchain installed (consensus, mempool validation,
#                        block generator execution, streamable types, BLS). It is rebuilt from that source and installed
#                        over the PyPI wheel, so a reproducer runs the same Rust code the agent can read.
#   /deps/clvm_rs        clvm_rs source at the clvmr version chia_rs links (the CLVM interpreter and cost model).
#   /root/.chia          the CI test-cache (pre-generated blocks and plots), so block-level tests run offline.
FROM python:3.12-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential clang pkg-config libssl-dev cmake git curl jq sqlite3 lsof procps gdb strace \
    && rm -rf /var/lib/apt/lists/*

# Rust, for rebuilding chia_rs from source. The toolchain each Rust repo pins in rust-toolchain.toml is installed
# when cargo first runs in that repo below, while the network is still up.
ENV RUSTUP_HOME=/opt/rustup CARGO_HOME=/opt/cargo PATH=/opt/cargo/bin:$PATH
RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable

# Line-table debug info and frame pointers in the Rust builds, for usable stack traces. chia_rs's release profile
# uses thin LTO; it is turned off here so release builds keep their debug info cheaply.
ENV RUSTFLAGS="-C force-frame-pointers=yes" \
    CARGO_PROFILE_RELEASE_DEBUG=1 \
    CARGO_PROFILE_RELEASE_STRIP=none \
    CARGO_PROFILE_RELEASE_LTO=false

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# chia-blockchain as its developers install it: poetry venv in /src/.venv with the dev extras (pytest, mypy, ...).
RUN ./install.sh -d
ENV VIRTUAL_ENV=/src/.venv PATH=/src/.venv/bin:$PATH

# chia_rs and clvm_rs source at the versions this checkout actually uses.
RUN CHIA_RS_VERSION="$(python -c 'import importlib.metadata as m; print(m.version("chia_rs"))')" \
    && git clone --quiet --branch "${CHIA_RS_VERSION}" https://github.com/Chia-Network/chia_rs /deps/chia_rs \
    && CLVMR_VERSION="$(grep -A1 '^name = "clvmr"$' /deps/chia_rs/Cargo.lock | sed -n 's/^version = "\(.*\)"$/\1/p' | head -1)" \
    && git clone --quiet --branch "${CLVMR_VERSION}" https://github.com/Chia-Network/clvm_rs /deps/clvm_rs \
    && echo "chia_rs ${CHIA_RS_VERSION} (clvmr ${CLVMR_VERSION})" | tee /deps/VERSIONS

# Every crate both Rust workspaces need. From here on cargo must not reach a registry, so the build itself shows the
# Rust side works offline.
RUN pip install --quiet 'maturin~=1.7' \
    && cd /deps/chia_rs && cargo fetch --locked \
    && cd /deps/clvm_rs && cargo fetch --locked
ENV CARGO_NET_OFFLINE=true

# Rebuild the chia_rs Python extension from /deps/chia_rs with debug info and install it over the PyPI wheel. If this
# fails the PyPI wheel of the same version stays installed, and the log says so.
RUN cd /deps/chia_rs \
    && ( maturin build --release --locked -m wheel/Cargo.toml -i /src/.venv/bin/python \
           --out /deps/wheels \
         && pip install --no-deps --force-reinstall /deps/wheels/chia_rs-*.whl \
         || echo "WARNING: chia_rs source build failed; the PyPI chia_rs wheel is still installed" ) \
    && python -c 'import chia_rs, importlib.metadata as m; print("chia_rs", m.version("chia_rs"), chia_rs.__file__)'

# The CI test-cache (about 1 GB): pre-generated blocks, plots and spend bundles that tests load from ~/.chia
# (blocks/, test-plots/, test-bundles/). Same version CI downloads, laid out the way CI lays it out.
RUN TEST_CACHE_VERSION="$(sed -n 's/^ *BLOCKS_AND_PLOTS_VERSION: *//p' .github/workflows/test-single.yml | head -1)" \
    && mkdir -p /root/.chia \
    && curl -fsSL --retry 5 "https://github.com/Chia-Network/test-cache/archive/refs/tags/${TEST_CACHE_VERSION}.tar.gz" \
       | tar -xz --strip-components=1 -C /root/.chia \
    && test -d /root/.chia/blocks && test -d /root/.chia/test-plots && test -d /root/.chia/test-bundles

# Smoke tests so the log shows the image works; a failure here does not fail the build. Kept to a few minutes: the
# full mempool suite alone runs past the build time limit, and the agent can run any test offline during the scan.
RUN chia version \
    && ( timeout 600 pytest -q -n 4 chia/_tests/clvm \
         || echo "WARNING: pytest smoke tests reported failures" )
