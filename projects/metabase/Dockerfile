# Metabase Open Source Edition: Clojure backend (JVM 25) + TypeScript/ClojureScript frontend.
# Follows the upstream builder stage in the repository's own Dockerfile, then also pre-fetches the dev/test
# classpath so the backend can be run from source and its tests run without network access.
FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    INTERACTIVE=false \
    HUSKY=0 \
    MB_EDITION=oss

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget gpg apt-transport-https git python3 rlwrap \
    && wget -qO - https://packages.adoptium.net/artifactory/api/gpg/key/public | gpg --dearmor > /etc/apt/trusted.gpg.d/adoptium.gpg \
    && echo "deb https://packages.adoptium.net/artifactory/deb bookworm main" > /etc/apt/sources.list.d/adoptium.list \
    && apt-get update && apt-get install -y --no-install-recommends temurin-25-jdk \
    && rm -rf /var/lib/apt/lists/*

# Clojure CLI (same installer version as the upstream Dockerfile), uv (bundles Python deps into the jar), bun.
RUN curl -fsSLO https://download.clojure.org/install/linux-install-1.12.0.1488.sh \
    && bash linux-install-1.12.0.1488.sh && rm linux-install-1.12.0.1488.sh \
    && curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh \
    && npm install -g bun@1.3.14
ENV PATH="/src/bin:$PATH"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src
RUN git config --global --add safe.directory /src

# Frontend dependencies.
RUN bun install --frozen-lockfile

# Open Source Edition uberjar (includes the frontend bundle and bundled drivers):
# target/uberjar/metabase.jar
RUN bin/build.sh '{:edition :oss}'

# Pre-fetch everything needed to run the backend from source and to run backend tests offline:
#   clojure -M:run:oss                                   (dev server from source)
#   clojure -X:dev:oss:oss-dev:test :only '[some.ns-test]' (tests; app DB is in-memory H2)
RUN clojure -P -M:dev:oss:oss-dev:drivers:drivers-dev:test:run

# Offline backend smoke test; report test failures without stopping the build.
RUN --network=none timeout 1200 clojure -X:dev:oss:oss-dev:test :only '[metabase.session.api-test]' \
    || echo "WARNING: smoke test reported failures"
