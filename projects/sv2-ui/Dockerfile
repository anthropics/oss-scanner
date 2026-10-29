# Scanner image for https://github.com/stratum-mining/sv2-ui.
#
# The audit runs offline, so this build installs every npm package and builds the frontend and the backend.
# threat_model.md, next to this file, says how to run each of them.

# Node.js 24, which is what the repository's CI, its own Dockerfile and AGENTS.md use.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Every package of the root package and its two npm workspaces (server, shared), from the lockfile.
RUN npm ci

# The frontend (tsc + vite) and the backend (tsc), as CI and the repository's Dockerfile build them. A step that
# fails fails the build, and primary_contact gets the log.
RUN npm run build && npm run build:server

# Run the tests so the log shows the image works, without letting a failure abort the build. (The type check is
# already covered: `build` runs the same `tsc` on a `noEmit` tsconfig.) check:sv2-app-config is left out: it pulls the
# sv2-apps Docker images, which the audit environment cannot do.
RUN (timeout 600 npm run test:all || echo "WARNING: tests reported failures")

# The server is an Express app that talks to a Docker daemon; there is none in the image, so it is not started here.
# NODE_ENV is left unset on purpose: without it the server serves the frontend from /src/dist, where this build put it.
ENV PORT=8080 CONFIG_DIR=/src/data/config
