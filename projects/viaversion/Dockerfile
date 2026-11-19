# ViaVersion (https://github.com/ViaVersion/ViaVersion), a Minecraft protocol translation layer.
FROM eclipse-temurin:25-jdk-noble
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# CI's build without the tests: fetches every dependency and plugin, compiles every module and test source set and builds the shaded jars.
RUN ./gradlew --no-daemon --console=plain build -x test

# The test suite loads the full platform with every protocol and its mappings.
RUN ./gradlew --no-daemon --console=plain --continue test \
    || echo "WARNING: the tests reported failures"

# Mark gradle build as offline.
RUN mkdir -p /root/.gradle/init.d \
    && echo 'gradle.startParameter.offline = true' > /root/.gradle/init.d/offline.gradle

# Show that a test runs offline in its final state.
RUN ./gradlew --no-daemon --console=plain :viaversion-common:test --rerun \
      --tests 'com.viaversion.viaversion.common.type.StringTypeTest' \
    || echo "WARNING: the offline test run reported failures"
