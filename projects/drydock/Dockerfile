# OSS Scanner build for Drydock (https://github.com/CodesWhat/drydock).
#
# This file lives next to project.yaml in the oss-scanner repository. The scanner copies it to .oss-scanner/Dockerfile
# in a fresh clone of Drydock's main branch and builds it with that clone as the context. The network is available
# only while this file builds; the scan itself runs offline.
#
# Drydock has no npm workspaces: the repository root, app/ and ui/ each have their own package.json and lockfile, and
# each needs its own `npm ci`. The install steps below are the ones the test job in .github/workflows/ci-verify.yml
# runs.
#
#   /src                 root tooling: Biome (app/ and ui/ run `biome check .` through it), and Vitest for the
#                        workflow tests in .github/tests
#   /src/app             backend (TypeScript, Express). Dependencies, then `npm run build` (tsc) into /src/app/dist
#   /src/ui              dashboard (Vue 3, Vite). Dependencies, then `npm run build` into /src/ui/dist
#   /src/app/dist/ui     link to /src/ui/dist. The server looks for the dashboard there, so `node dist/index.js` in
#                        /src/app serves the API and the UI together
#
# Nothing here fetches at test time. The UI's icon bundle and font files are generated from packages that `npm ci`
# already installed (ui/scripts/extract-icons.mjs, extract-fonts.mjs), and no package.json sets packageManager, so
# corepack never downloads a package manager.
#
# Left out on purpose:
#   e2e/                 Cucumber and Playwright suites. They need a Docker daemon, a compose stack, registry pulls and
#                        downloaded browsers, none of which exist in an offline scan.
#   apps/web, apps/demo  the marketing/docs site and the public demo. Neither is part of the shipped image.
#   Trivy and cosign     the release image bundles both for vulnerability scans and signature checks. They work against
#                        online databases and registries, so they are not installed here. app/security is still built
#                        and its tests (which stub both binaries) still run.
#   a Docker daemon      the backend tests stub the Docker API. threat_model.md says how to drive a running server.
#
# The published image is built from the repository's own Dockerfile on node:24-alpine. This one uses Debian so the
# scanner's tools install from apt; the code under test is the same.
FROM node:24-bookworm-slim

# The npm settings only stop npm from phoning home (update check, funding and audit lookups) on later commands.
ENV DEBIAN_FRONTEND=noninteractive \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false

# gcc and libc6-dev: app/healthcheck.binary.test.ts compiles healthcheck.c with `cc`. git and jq: the release scripts
# under scripts/ and .github/ shell out to both, and so do their tests.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git gcc libc6-dev jq \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Dependencies first, from the lockfiles alone, so these layers are reused until a lockfile changes.
# --ignore-scripts at the root (as CI does) skips the `prepare` script, which would install lefthook's git hooks.
COPY package.json package-lock.json /src/
RUN npm ci --ignore-scripts && rm -rf /root/.npm

COPY app/package.json app/package-lock.json /src/app/
RUN cd /src/app && npm ci && rm -rf /root/.npm

COPY ui/package.json ui/package-lock.json /src/ui/
RUN cd /src/ui && npm ci && rm -rf /root/.npm

# scanner contract: the checkout lives inside the image, at /src. The scanner removes the repository's .dockerignore
# before it builds, so the tests, scripts/ and .git are all part of this copy.
COPY . /src

# Keep the work tree clean, so `git status` is quiet and a patch made with `git diff` holds only the fix: put back the
# .dockerignore the scanner deleted from the context, and hide the .oss-scanner/ directory it added.
RUN (git -C /src checkout -- .dockerignore && echo '.oss-scanner/' >> /src/.git/info/exclude) \
    || echo "WARNING: could not tidy the git work tree"

# Backend: tsc, then the static assets are copied into dist/.
RUN cd /src/app && npm run build

# Dashboard: icon bundle, lazy-loaded fonts, then the vite build. The icon step rewrites the tracked
# ui/src/boot/icon-bundle.json; restore the committed copy afterwards, for the same reason as above.
RUN cd /src/ui && npm run build \
    && (git -C /src checkout -- ui/src/boot/icon-bundle.json || true) \
    && ln -sfn ../../ui/dist /src/app/dist/ui

# Smoke tests, so the log shows whether the image works. Each workspace's `test:security` script is a small, fast subset
# of its suite. Failures are printed but never fail the build. The full suites are left for the scan, where they take
# a few minutes each on two CPUs:
#   cd /src/app && npx vitest run            (about 430 files, one at a time)
#   cd /src/ui  && npx vitest run            (about 230 files, jsdom)
RUN (cd /src/app && timeout 10m npm run test:security \
       || echo "WARNING: app test:security reported failures or ran out of time") \
    && (cd /src/ui && timeout 10m npm run test:security \
       || echo "WARNING: ui test:security reported failures or ran out of time") \
    && (git -C /src status --short || true)
