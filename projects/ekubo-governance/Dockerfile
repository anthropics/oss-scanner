# Ekubo governance: Cairo package (Scarb + Starknet Foundry) and a Foundry project in l1_proxy/.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git build-essential python3 jq \
    && rm -rf /var/lib/apt/lists/*

# Toolchains pinned to .tool-versions (scarb 2.20.0, starknet-foundry 0.62.1) and CI (forge v1.5.1).
ENV PATH=/root/.cargo/bin:/root/.local/bin:/opt/foundry/bin:$PATH FOUNDRY_DIR=/opt/foundry
# snforge compiles its Scarb plugin with cargo.
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal \
    && cargo --version
RUN curl --proto '=https' --tlsv1.2 -sSf https://docs.swmansion.com/scarb/install.sh | sh -s -- -v 2.20.0 \
    && curl -fsSL https://raw.githubusercontent.com/foundry-rs/starknet-foundry/master/scripts/install.sh | sh \
    && /root/.local/bin/snfoundryup -v 0.62.1 \
    && curl -fsSL https://raw.githubusercontent.com/software-mansion/universal-sierra-compiler/master/scripts/install.sh | sh \
    && scarb --version && snforge --version
RUN curl -fsSL https://foundry.paradigm.xyz | bash \
    && /opt/foundry/bin/foundryup --install v1.5.1 && forge --version

COPY . /src
WORKDIR /src
RUN git submodule update --init --recursive

# Fetch registry dependencies and compile everything while the network is up.
RUN scarb fetch && scarb build && (cd l1_proxy && forge build --sizes)

# Run the tests once so snforge's caches are warm offline; never fail the image on a test.
RUN (timeout 1500 snforge test || echo "WARNING: snforge test reported failures or timed out")
RUN (cd l1_proxy && timeout 600 forge test --offline -q || echo "WARNING: forge test reported failures or timed out")
