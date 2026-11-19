# OSS Scanner build for EtherCalc (audreyt/ethercalc).
#
# Build context is the EtherCalc checkout. The scanner builds this image
# with network access, then audits it with no Internet access, so every
# dependency the build or the tests need is fetched here.
#
# This mirrors the repository's own self-host Dockerfile (oven/bun:1.3.14,
# client builds, curated assets/) minus the runtime concerns (VOLUME,
# entrypoint, workerd bundle). `vp` (Vite+) is a workspace devDependency,
# so build/test commands run through ./node_modules/.bin/vp.

FROM oven/bun:1.3.14

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# Install every workspace including devDependencies (vitest, wrangler,
# workerd) so the audit can run the suites offline. --ignore-scripts skips
# the packed-package postinstall, which would otherwise prune to
# production-only dependencies now that .dockerignore excludes .git.
RUN bun install --frozen-lockfile --ignore-scripts

# Build the single-sheet + multi-sheet client bundles and the curated
# assets/ tree served by the Worker.
RUN bun run --cwd packages/client build \
 && bun run --cwd packages/client-multi build \
 && ./scripts/build-assets.sh

# Cheap self-test so we know the image works. Failures warn rather than
# fail the build, per the scanner template; the full suites are listed in
# threat_model.md ("How to exercise it").
RUN ./node_modules/.bin/vp run @ethercalc/shared#test || echo "WARNING: @ethercalc/shared tests reported failures"
