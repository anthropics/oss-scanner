# Caffeine (https://github.com/ben-manes/caffeine), a caching library for Java.
#
# The Gradle build provisions its own JDKs as toolchains: the daemon and the compiler use the
# version in gradle/gradle-daemon-jvm.properties, the build logic uses 25, the tests use 11 (the
# minimum supported) unless -PjavaTestVersion says otherwise, and Fray instruments a Corretto 25.
# Gradle downloads each one below, while there is a network, so this file names none of them
# beyond the 25 that runs the wrapper.
FROM eclipse-temurin:25-jdk-noble
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# JDK25_HOME is one of the installations that gradle.properties reads from the environment, so the
# build logic compiles on this image's JDK. lint=false turns off ErrorProne and NullAway, as in
# CI's test jobs, so that a reproducer compiles without satisfying the project's static analysis.
ENV JDK25_HOME=/opt/java/openjdk \
    ORG_GRADLE_PROJECT_lint=false

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# CI's first step: fetch every external dependency and compile every source set, including the
# code generator and each test suite. Javadoc is left out because it reads from external sites.
RUN ./gradlew --no-daemon --console=plain resolveExternalDependencies assemble \
      -x javadoc -x javadocJar

# One quick test from each suite that the threat model points to. Running them downloads what
# compiling does not: the test JDK, Fray's JDK and its instrumented copy, and the agents that the
# test tasks attach. A failing test does not abort the build.
RUN ./gradlew --no-daemon --console=plain --continue \
      :caffeine:test --tests 'com.github.benmanes.caffeine.cache.FrequencySketchTest' \
      :caffeine:lincheckTest --tests 'com.github.benmanes.caffeine.cache.PacerLincheckTest' \
      :caffeine:frayTest \
        --tests 'com.github.benmanes.caffeine.cache.EvictionFrayTest.concurrentRemove_sameKey' \
      :guava:test --tests 'com.github.benmanes.caffeine.guava.CaffeinatedGuavaTest' \
      :jcache:test --tests 'com.github.benmanes.caffeine.jcache.copy.JavaSerializationCopierTest' \
    || echo "WARNING: the warm-up tests reported failures"

# The scan has no network. This init script makes every later build offline, so that a forgotten
# --offline cannot stall on a repository lookup.
RUN mkdir -p /root/.gradle/init.d \
    && echo 'gradle.startParameter.offline = true' > /root/.gradle/init.d/offline.gradle

# Show that a test runs with what the image holds.
RUN ./gradlew --no-daemon --console=plain :caffeine:test --rerun \
      --tests 'com.github.benmanes.caffeine.cache.FrequencySketchTest' \
    || echo "WARNING: the offline test run reported failures"
