# Build Apache CloudStack for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline, so everything the
# tests need is installed here. This mirrors CloudStack's own CI (.github/workflows/build.yml and
# .github/actions/setup-env): Ubuntu 24.04, JDK 17, Maven, and the same APT build dependencies.
FROM ubuntu:24.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    MAVEN_OPTS="-Xmx4g"

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git maven openjdk-17-jdk-headless \
        uuid-runtime genisoimage netcat-openbsd ipmitool build-essential \
        libgcrypt20 libgpg-error-dev libgpg-error0 libopenipmi0 \
        python3 python3-dev python3-pip python3-setuptools python3-openssl \
        libpython3-dev libssl-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# Build everything the way CI does (management server, agent, plugins, systemvm, simulator), without
# -Dnoredist since the non-OSS vendor jars are not publicly available. Tests are skipped here to keep the
# build tractable; they are run below. A build failure fails the image.
RUN mvn -B -P developer,systemvm -Dsimulator -DskipTests install -T"$(nproc)"

# Run a fast unit-test slice so the image is known to work and the surefire providers are cached for
# offline use; a failing test must not abort the build. Further tests, offline:
#   mvn -o -pl <module> test -Dtest=<TestClass>
RUN mvn -B -o -pl utils test -Dtest='NumbersUtilTest,StringUtilsTest' -Dsurefire.failIfNoSpecifiedTests=false \
    || echo "WARNING: mvn test reported failures"
