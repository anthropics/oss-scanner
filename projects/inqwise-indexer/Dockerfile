FROM maven:3.9-eclipse-temurin-21
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 curl \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the repository checkout and build artifacts live at /src.
COPY . /src
WORKDIR /src

# Build the complete reactor, including the reference application and web console.
# Maven's frontend plugin installs its pinned Node/npm and populates the npm cache.
# Keep Maven's local repository and npm's cache for offline tests and reproducers.
RUN mvn -B -ntp install -DskipTests

# Resolve test-provider dependencies online, then verify the cached offline build.
# Test failures remain visible without preventing the security audit.
RUN mvn -B -ntp test || echo "WARNING: Maven tests reported failures"
RUN npm_config_offline=true mvn -B -ntp -o test \
    || echo "WARNING: offline Maven tests reported failures"
RUN cd indexer-web/src/main/frontend \
    && PATH="/src/indexer-web/target/node:$PATH" npm test \
    || echo "WARNING: frontend tests reported failures"
