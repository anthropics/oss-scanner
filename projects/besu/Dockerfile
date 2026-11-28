# Besu builds with Java 25 (gradle/gradle-daemon-jvm.properties) and the Gradle wrapper.
FROM eclipse-temurin:25-jdk-noble

ENV DEBIAN_FRONTEND=noninteractive \
    GRADLE_OPTS="-Dorg.gradle.daemon=false"

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Build the node distribution (build/install/besu) and evmtool, and compile every test source set, so that every
# dependency the scan may need is in the Gradle cache before the network is removed.
RUN ./gradlew installDist :ethereum:evmtool:installDist testClasses integrationTestClasses jmhClasses

# Fetch what running tests and the formatter needs (the JUnit launcher, Spotless's google-java-format), by running a
# few quick test suites. Failures here must not fail the build.
RUN (./gradlew :ethereum:rlp:test :crypto:algorithms:test :ethereum:p2p:test --tests '*discovery.dns*' \
      || echo "WARNING: some tests failed") \
    && (./gradlew spotlessCheck || echo "WARNING: spotlessCheck reported problems")
