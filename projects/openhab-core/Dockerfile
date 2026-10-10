FROM eclipse-temurin:21-jdk-jammy
ENV DEBIAN_FRONTEND=noninteractive \
    MAVEN_OPTS="-Xmx2g -Dmaven.wagon.http.retryHandler.count=5 -Dmaven.wagon.httpconnectionManager.ttlSeconds=25 -Dorg.slf4j.simpleLogger.log.org.apache.maven.cli.transfer.Slf4jMavenTransferListener=warn"
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates bc unzip curl \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image at /src.
COPY . /src
WORKDIR /src

# Match openHAB Core's Java 21 static-analysis CI build. Integration tests include Linux sysfs hardware
# discovery and are not reliable in the scanner's containerized build environment.
RUN ./.github/scripts/maven-build install -B -T 1.25C -U \
    -Dspotless.check.skip=true -Dmaven.test.skip=true -Dfeatures.verify.skip=true
