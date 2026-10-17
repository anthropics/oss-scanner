# OSS Scanner build for Origin Dollar (OUSD / OETH smart contracts).
#
#   /src/contracts   Foundry project (Solidity 0.8.28). All commands run from here.
#                    Contracts:   contracts/   (vault/, token/, strategies/, ...)
#                    Unit tests:  tests/unit/  -> make test-unit
#                                 one contract: forge test --match-contract <Name> -vvv
#                    Mocks:       contracts/mocks/, tests/mocks/
#
# Fork and smoke tests (tests/fork, tests/smoke) need an RPC endpoint and cannot run offline;
# reproduce findings as unit tests against mocks instead.
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git make jq python3 \
    && rm -rf /var/lib/apt/lists/*

# Foundry, pinned to the version the repo uses (contracts/Makefile `install`).
ENV PATH="/root/.foundry/bin:${PATH}"
RUN curl -fsSL https://foundry.paradigm.xyz | bash \
    && foundryup --install v1.8.3 \
    && forge --version

# pnpm, pinned via contracts/package.json `packageManager`.
RUN corepack enable

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src/contracts

# Solidity dependencies (soldeer + the CCIP tarball) and JS tooling. The solc 0.8.28 binary
# is downloaded by the first forge build below, while the network is still available.
RUN ./install-deps.sh \
    && CI=true pnpm install --frozen-lockfile

RUN forge build contracts/ tests/unit/ tests/mocks/

# Smoke-check the image; failures must not abort the build.
RUN FOUNDRY_MATCH_PATH='tests/unit/**' forge test --summary || echo "WARNING: unit tests reported failures"
