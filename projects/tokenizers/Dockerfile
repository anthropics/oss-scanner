# Scanner image for https://github.com/huggingface/tokenizers.
#
# The audit runs offline, so this build fetches every crate, the test fixtures from the Hugging Face Hub and the Python
# dependencies, builds the Rust workspace with all features and its tests, and installs the Python bindings into
# /src/bindings/python/.venv. threat_model.md says how to run each of them.

# Stable Rust, which is what rust-toolchain pins. bitcannon needs 1.89 or newer.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
# clang for the C and C++ dependencies (onig, esaxx); libssl-dev for the `http` feature's TLS stack.
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends clang libssl-dev pkg-config python3 python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /uvx /usr/local/bin/

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# An ARG, so that it bounds the memory this build uses without reaching the audit environment.
ARG CARGO_BUILD_JOBS=8
ENV CARGO_PROFILE_RELEASE_DEBUG=true \
    RUST_BACKTRACE=1 \
    UV_LINK_MODE=copy \
    PATH=/src/bindings/python/.venv/bin:$PATH
ARG HF="uvx --from huggingface_hub hf"

# Every crate, and the fixtures `make test` and `make oracle` read (pinned by HF_REVISION in tokenizers/Makefile).
RUN cd /src/tokenizers && cargo fetch \
    && make data HF="$HF" \
    && make HF="$HF" $(echo 'print-oracle: ; @echo $(ORACLE_RESOURCES)' | make -s -f Makefile -f - print-oracle) \
    && cd /src/bindings/python && cargo fetch \
    && make test-data HF="$HF" \
    && uv sync --no-install-project --python /usr/bin/python3

# The workspace with all features, its tests (including the oracle against the released crate), and the Python
# extension. A step that fails fails the build, and primary_contact gets the log.
RUN cd /src/tokenizers && cargo build --workspace --all-targets --all-features \
    && cargo test --workspace --all-features --no-run \
    && cargo test -p tk-convert --features bench-baseline --test oracle --no-run \
    && cd /src/bindings/python && maturin develop --release --uv

# Run the tests so the log shows the image works, without letting a failure abort the build.
RUN (cd /src/tokenizers && timeout 1800 cargo test --workspace --no-fail-fast || echo "WARNING: cargo test reported failures") \
    && (cd /src/tokenizers && timeout 900 cargo test -p tk-convert --features bench-baseline --test oracle \
        || echo "WARNING: the oracle tests reported failures") \
    && (cd /src/bindings/python && timeout 900 pytest -q -m "not network" tests \
        || echo "WARNING: pytest reported failures")

# Everything is fetched. From here on cargo must not wait for a registry that it cannot reach.
ENV CARGO_NET_OFFLINE=true \
    HF_HUB_OFFLINE=1
