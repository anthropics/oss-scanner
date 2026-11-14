# Build Bahmni Core for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline, so every Maven dependency
# and plugin is fetched here. This mirrors Bahmni's own CI (.github/workflows): JDK 8 and the Maven wrapper.
FROM eclipse-temurin:8-jdk

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/root \
    MAVEN_OPTS="-Xmx2g"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build every module and install it into ~/.m2 so later offline runs resolve the sibling modules. Tests are
# skipped here to keep the build tractable; a slice of them runs below. A build failure fails the image.
RUN ./mvnw -B --no-transfer-progress clean install -DskipTests

# Run a unit-test slice while still online so the surefire JUnit provider and test dependencies are cached for
# offline use, and the image is known to work; a failing test must not abort the build. Further tests, offline:
#   ./mvnw -o -pl <module> test -Dtest=<TestClass>
RUN ./mvnw -B --no-transfer-progress -pl bahmni-emr-api test \
    || echo "WARNING: mvn test reported failures"
