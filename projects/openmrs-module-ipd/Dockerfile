# Builds the Bahmni IPD backend (openmrs-module-ipd), a two-module Maven project (api + omod) that produces an
# OpenMRS module (.omod). The repo's CI uses JDK 17 (temurin) and the checked-in Maven wrapper (./mvnw).
FROM eclipse-temurin:17-jdk-jammy
ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8
# The UTF-8 settings above guard against the pom having no sourceEncoding: under a POSIX locale Java 17 reads files as ASCII,
# which made resource filtering of api/src/main/resources/liquibase.xml fail (MalformedInputException) on a Debian base.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build and install both modules, skipping tests. This runs online, so it also downloads the Maven distribution used by
# the wrapper and every compile-time dependency (OpenMRS platform, webservices.rest, FHIR2, bed-management, ...) into
# ~/.m2 for the offline audit that follows.
RUN ./mvnw -B -ntp -DskipTests install

# Run the unit tests so the surefire/test dependencies are cached too, but do not let a failing test abort the build.
RUN ./mvnw -B -ntp test || echo "WARNING: mvn test reported failures"
