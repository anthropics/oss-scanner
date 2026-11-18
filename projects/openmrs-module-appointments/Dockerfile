# Builds openmrs-module-appointments (Maven wrapper 3.8.4; api + atom-feed + omod). Platform 2.8.x, CI uses JDK 17.
FROM eclipse-temurin:17-jdk-jammy
ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Online step: compile and install, which also caches the Maven distribution and all dependencies for the offline audit.
RUN ./mvnw -B -ntp -DskipTests install

# Run the unit tests so the test dependencies are cached, but do not let a failing test abort the build.
RUN ./mvnw -B -ntp test || echo "WARNING: mvn test reported failures"
