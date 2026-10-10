# Seclume: multi-module Maven build, Java 25 (Temurin), Maven wrapper in the repo.
# Network is available during this build only, so all dependencies are fetched here.
FROM eclipse-temurin:25-jdk
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Compile every module (including tests) and install into ~/.m2, which also downloads the dependencies the scan
# will need offline. Tests that need a database skip themselves, so this does not depend on any server.
RUN ./mvnw -B -ntp -DskipTests install

# Warm the plugin and test-runtime caches for offline use.
RUN ./mvnw -B -ntp dependency:go-offline || echo "WARNING: dependency:go-offline reported problems"

# Run the tests that need no server so you know the image works, but do not abort the build on failures.
RUN (./mvnw -B -ntp -o test || echo "WARNING: mvn test reported failures")
