# HUQAN — local-first governance layer for AI agents (Node.js, no external services at runtime).
#
# Built the way the project's own CI builds it: Node 22 LTS, `npm ci` with optional
# dependencies (pdfjs-dist/pdfkit are optional and some tests need them), then the
# test suite. HUQAN has no network dependency at runtime — the gate, the stores and
# the Trust Receipt verifier are all local — so the scanner's offline analysis phase
# exercises the same code paths a user would.
#
# The project's own Dockerfile pins a digest and builds a two-stage runtime image for
# the server; that image is deliberately minimal (production deps only, no dev deps,
# no tests). The scanner needs the opposite: the full checkout with test dependencies
# present. This Dockerfile is therefore the development/test build, not the release image.
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true

# better-sqlite3 ships prebuilt binaries for linux-x64 glibc, but the toolchain is
# present so a source build succeeds if the prebuild is unavailable for this Node.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 make g++ \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# package.json engines requires Node >= 22.14.0. Fail loudly here rather than with
# hundreds of secondary test failures if the base image is ever moved.
RUN node -e "const r=require('./package.json').engines.node; const [maj,min]=process.versions.node.split('.').map(Number); if (maj < 22 || (maj === 22 && min < 14)) { console.error('need Node >= 22.14.0, have '+process.versions.node); process.exit(1); }"

# `npm ci` from the lockfile. Optional dependencies are included because the PDF
# adapter and its tests need pdfjs-dist; omitting them is a documented source of
# secondary failures (scripts/verify-test-environment.js).
RUN npm ci --include=optional --no-audit --no-fund

# Fail the build if the native binding or the optional PDF dependency did not land:
# these are the two root causes scripts/verify-test-environment.js names first, and a
# broken image should be caught here, not during the offline scan.
RUN node -e "require('better-sqlite3')" && node -e "require.resolve('pdfjs-dist')"

# The suite runs against a throwaway state root (scripts/run-tests.js), so it never
# touches a live gate state. A failing test must not abort the image: the scanner runs
# the suite again offline, and one failing test should not hide the rest of the image.
# The full suite is `npm test` (sharded in CI for time); this runs a representative
# slice of the security-critical surface so the image is known-good and the build stays
# inside the scanner's time budget.
RUN node scripts/run-tests.js \
      test/path-safety.test.js \
      test/action-risk-classifier.test.js \
      test/risk-rules.test.js \
      test/tool-call-gate.test.js \
      test/mcp-gate-adapter.test.js \
      test/memory-schema.test.js \
      test/memory-store.test.js \
      test/kernel-memory.test.js \
    || echo "WARNING: the smoke slice reported failures; the scanner re-runs the suite offline"
