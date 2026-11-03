# Builds Lista Moolah the way its CI does (.github/workflows/unit-tests.yaml): Foundry v1.8.1, submodules,
# and the node_modules of lib/lista-dao-contracts.git that remappings.txt points into.
# node:20-bookworm already ships git, curl, python3 and yarn 1.x.
FROM node:20-bookworm

# Pinned to the version CI uses; newer releases change vm.expectRevert matching and fail several suites.
ENV FOUNDRY_DIR=/root/.foundry \
    PATH="/root/.foundry/bin:${PATH}"
RUN curl -fsSL https://foundry.paradigm.xyz | bash \
    && foundryup --install v1.8.1 \
    && forge --version

COPY . /src
WORKDIR /src

RUN git submodule update --init --recursive
RUN cd lib/lista-dao-contracts.git && yarn install --frozen-lockfile --ignore-scripts

# Downloads solc 0.8.34 into ~/.svm, so later builds work offline. Compiling src, tests and scripts together
# under via-IR needs more than 8 GB, so build src here and run tests one path at a time with --match-path,
# which compiles only the files that path needs.
ENV FOUNDRY_PROFILE=ci
RUN forge build --skip test --skip script

# Smoke-test the core market suites offline (fork tests need a BSC/ETH RPC); do not fail the build on test failures.
RUN forge test --offline --match-path "test/moolah/integration/*" \
    || echo "WARNING: forge test reported failures"
