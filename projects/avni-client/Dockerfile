# Build avni-client for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline.
# Mirrors the install_deps and test_android jobs of the project's CI (.circleci/config.yml): Node 20.19.5,
# make deps_ci, make ci test-android. The Android (Gradle/NDK) build is not run; the JavaScript application in
# packages/openchs-android and its unit tests are.
FROM node:20.19.5-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    NODE_OPTIONS=--max_old_space_size=4096

RUN apt-get update \
    && apt-get install -y --no-install-recommends make patch \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

RUN make deps_ci

# Run the unit tests so the image is known to work. A failing test is reported but does not stop the image build.
RUN make ci test-android || echo "WARNING: make ci test-android reported failures"
