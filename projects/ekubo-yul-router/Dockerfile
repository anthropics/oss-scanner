# Ekubo Yul router: Foundry project (submodules incl. evm-contracts) plus a Bun/TypeScript SDK in sdk/.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip build-essential python3 jq \
    && rm -rf /var/lib/apt/lists/*

ENV FOUNDRY_DIR=/opt/foundry BUN_INSTALL=/opt/bun PATH=/opt/foundry/bin:/opt/bun/bin:$PATH
# Foundry pinned to v1.8.3 (as in evm-contracts CI). forge prints a harmless parse diagnostic for src/YulRouter.yul.
RUN curl -fsSL https://foundry.paradigm.xyz | bash && /opt/foundry/bin/foundryup --install v1.8.3 && forge --version
RUN curl -fsSL https://bun.sh/install | bash -s "bun-v1.3.11" && bun --version

COPY . /src
WORKDIR /src
RUN git submodule update --init --recursive

RUN forge build --sizes
RUN cd sdk && bun install --frozen-lockfile && (bun run build || echo "WARNING: sdk build failed")

RUN (timeout 1200 forge test --offline || echo "WARNING: forge test reported failures or timed out")
RUN (cd sdk && timeout 600 bun run test || echo "WARNING: bun test reported failures or timed out")
