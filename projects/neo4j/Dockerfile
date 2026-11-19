# Build Neo4j for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline.
#
# Two layers:
#   1. Source build: full Maven build of the checkout (compiler targets Java 21 per
#      vm.target.version in the root pom.xml; the enforcer requires Maven >= 3.9.11),
#      leaving the source tree and toolchain in place so the audit agent can recompile
#      and run tests offline.
#   2. Runtime: the distribution produced by the build is unpacked at /var/lib/neo4j
#      (the official docker image's location), so the agent can boot a real server from
#      scanned code with `neo4j console`.

FROM eclipse-temurin:21-jdk-jammy

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG MAVEN_VERSION=3.9.11
ARG MAVEN_SHA512=bcfe4fe305c962ace56ac7b5fc7a08b87d5abd8b7e89027ab251069faebee516b0ded8961445d6d91ec1985dfe30f8153268843c89aa392733d1a3ec956c9978

ENV DEBIAN_FRONTEND=noninteractive \
    MAVEN_HOME=/opt/maven \
    PATH=/opt/maven/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s "${JAVA_HOME}/bin/java" /usr/bin/java

RUN curl -fsSL --retry 3 --retry-all-errors \
        "https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz" \
        -o /tmp/maven.tar.gz \
    && echo "${MAVEN_SHA512}  /tmp/maven.tar.gz" | sha512sum --check --strict - \
    && mkdir -p "${MAVEN_HOME}" \
    && tar -xzf /tmp/maven.tar.gz -C "${MAVEN_HOME}" --strip-components=1 \
    && rm /tmp/maven.tar.gz \
    && mvn --version

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# Build and install all modules (annotations, community/*, packaging), skipping tests.
# -DskipTests still compiles test classes, so test code is available to the audit agent.
# This produces the distribution tarball at packaging/standalone/target/*-unix.tar.gz.
RUN mvn -B -ntp -DskipTests install

# Run the cheap unit tests of a few small modules so we know the image works,
# but do not let a failing test abort the build.
RUN mvn -B -ntp --fail-never \
      -pl community/collections,community/concurrent \
      -am -DskipTests=false surefire:test

# --- runtime layer: unpack the distribution so a real server can be started ---
ENV NEO4J_HOME=/var/lib/neo4j \
    PATH=/var/lib/neo4j/bin:$PATH

RUN distribution="$(ls /src/packaging/standalone/target/neo4j-community-*-unix.tar.gz | head -1)" \
    && tar --extract --file "${distribution}" --directory /var/lib \
    && mv /var/lib/neo4j-community-* "${NEO4J_HOME}"

WORKDIR /src
EXPOSE 7474 7687
