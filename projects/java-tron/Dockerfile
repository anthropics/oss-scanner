# syntax=docker/dockerfile:1
# Build image for java-tron. The scanner builds this with the java-tron checkout as the build context,
# then removes network access, so every dependency the build and the tests need is fetched here.
#
# java-tron requires JDK 8 on x86_64 and JDK 17 on aarch64, and the build fails fast on a mismatch
# (see AGENTS.md). The scanner runs on x86_64 and gets JDK 8; the arm64 stage only exists so that
# tools/check also works on Apple Silicon.
ARG TARGETARCH
FROM eclipse-temurin:8-jdk-jammy AS jdk-amd64
FROM eclipse-temurin:17-jdk-jammy AS jdk-arm64
FROM jdk-${TARGETARCH}

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

ENV GRADLE_OPTS="-Dorg.gradle.daemon=false"

# Build every module and compile the tests, so later offline runs only execute.
RUN ./gradlew --no-daemon build -x test -x check \
    && ./gradlew --no-daemon testClasses

# Run a few cheap tests across the TVM, storage and networking modules. This checks that the image works
# and resolves the test runtime dependencies into ~/.gradle for offline use. A failure does not stop the build.
RUN timeout 1800 ./gradlew --no-daemon \
      :actuator:test --tests 'org.tron.core.vm.program.StorageAliasTest' \
      :framework:test --tests 'org.tron.common.runtime.vm.OptimizeTvmStorageTest' \
      :p2p:test --tests 'org.tron.p2p.connection.ChannelManagerTest' \
    || echo "WARNING: java-tron tests reported failures"
