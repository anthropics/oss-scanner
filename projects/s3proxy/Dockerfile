# S3Proxy (https://github.com/gaul/s3proxy), an HTTP server in Java that answers the Amazon S3 API
# from another store: memory, a local filesystem, SFTP, Azure Blob, Google Cloud Storage, OpenStack
# Swift, or S3 itself.
#
# CI builds and tests on Temurin 25 (the bytecode targets 17) with Maven 3.9, which the build's
# njord extension needs. The repository's own Dockerfile builds the release image from a jar built
# outside it, so this one builds from source instead.
FROM docker.io/library/maven:3.9-eclipse-temurin-25-noble
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# CI's build: compile with Error Prone and NullAway, run Checkstyle, SpotBugs and Modernizer, and
# assemble the executable jar target/s3proxy.
RUN mvn -B -ntp verify -DskipTests

# CI's first test lane: the whole JUnit suite against the in-memory store, each test starting its
# own proxy on a loopback port. It takes a few minutes and downloads Surefire's JUnit provider. A
# failing test does not abort the build.
RUN mvn -B -ntp test || echo "WARNING: mvn test reported failures"

# s3-tests (a fork of Ceph's S3 conformance suite) is a submodule that the scanner's clone leaves
# out. CI runs it through tox, which installs its packages on each run, so install them into a
# venv here instead; threat_model.md says how to run a test from it.
RUN (git submodule update --init --depth 1 s3-tests \
      && python3 -m venv /opt/s3-tests \
      && /opt/s3-tests/bin/pip install --no-cache-dir -r s3-tests/requirements.txt \
      && /opt/s3-tests/bin/pip install --no-cache-dir --no-deps -e s3-tests) \
    || echo "WARNING: s3-tests is not available"

# The scan has no network. This makes every later Maven run offline, so that a forgotten -o cannot
# stall on a repository lookup.
RUN mkdir -p /root/.m2 \
    && printf '<settings><offline>true</offline></settings>\n' > /root/.m2/settings.xml

# Show that a test runs with what the image holds.
RUN mvn -B -ntp test -Dtest=CopySourceAuthorizationTest \
    || echo "WARNING: the offline test run reported failures"
