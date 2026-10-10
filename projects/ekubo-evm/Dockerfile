# Ekubo Protocol EVM contracts: Foundry project (solc 0.8.33, via-IR), dependencies in git submodules.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential python3 python3-pip python3-venv jq \
    && rm -rf /var/lib/apt/lists/*

# Foundry, pinned to the version CI uses (.github/workflows/test.yml).
ENV FOUNDRY_DIR=/opt/foundry PATH=/opt/foundry/bin:$PATH
RUN curl -fsSL https://foundry.paradigm.xyz | bash \
    && /opt/foundry/bin/foundryup --install v1.8.3 \
    && forge --version

COPY . /src
WORKDIR /src

# lib/forge-std and lib/solady are submodules; the scanner's clone is not recursive.
RUN git submodule update --init --recursive

# Fetch solc 0.8.33 and compile everything (src, test, script) while the network is up.
RUN forge build --sizes

# Smoke-test the image without failing the build; the full suite is long under via-IR.
RUN (timeout 1200 forge test --offline -q || echo "WARNING: forge test reported failures or timed out")
