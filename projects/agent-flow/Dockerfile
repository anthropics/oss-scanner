# agent-flow: a Node.js CLI, Pi extension and git hooks that guard coding agents. Zero runtime dependencies;
# the devDependencies (TypeScript, the Pi SDK) are fetched here because the network is gone after this build.
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# The test suite creates real git repositories and commits in temp directories.
RUN git config --global user.email scanner@example.com && git config --global user.name scanner

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Compile extensions/**/*.ts to .js (the shipped build output) and link the CLI as `agent-flow`.
RUN npm ci && npm run build && npm link

# Run the tests so you know the image works, but do not let a failure abort the build.
RUN (node --test || echo "WARNING: npm test reported failures")
