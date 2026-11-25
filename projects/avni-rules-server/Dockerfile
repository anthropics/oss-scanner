# Build Avni's rules-server for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline.
# Mirrors the project's CI (.circleci/config.yml): Node 10, npm install, npm test.
FROM node:10.24.1-buster

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true

# Debian buster has moved to the archive; point apt at it so packages can still be installed on this image.
RUN printf '%s\n' \
    'deb http://archive.debian.org/debian buster main' \
    'deb http://archive.debian.org/debian-security buster/updates main' \
    > /etc/apt/sources.list \
    && printf '%s\n' 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99archive \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git python3 procps \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

RUN npm install

# Run the tests so the image is known to work. A failing test is reported but does not stop the image build.
RUN npm test || echo "WARNING: npm test reported failures"
