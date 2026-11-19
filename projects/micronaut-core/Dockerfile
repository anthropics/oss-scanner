# OSS Scanner build for micronaut-core (https://github.com/micronaut-projects/micronaut-core).
#
# The build is a multi-project Gradle build on Java 25. CI (.github/workflows/gradle.yml) runs it on GraalVM for
# JDK 25 with `./gradlew check`, which takes far longer than the scanner's 45-minute build limit. This image
# therefore compiles every module and its tests, caches every dependency, and leaves the tests themselves to be
# run offline afterwards with `./gradlew --offline <task>` (see threat_model.md).
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip zip bash procps python3 \
    && rm -rf /var/lib/apt/lists/*

# GraalVM Community for JDK 25, which is what the maintainers build and test with (CONTRIBUTING.md, .sdkmanrc).
# The release tag is graal-<version>; the tarball inside is named after the JDK release it ships.
ARG GRAALVM_RELEASE=graal-25.4.4.1.1
ARG GRAALVM_JDK=jdk-25i4-25.0.4.1.1
RUN set -eux; \
    case "$(dpkg --print-architecture)" in \
      amd64) arch=x64 ;; \
      arm64) arch=aarch64 ;; \
      *) echo "unsupported architecture: $(dpkg --print-architecture)"; exit 1 ;; \
    esac; \
    url="https://github.com/graalvm/graalvm-ce-builds/releases/download/${GRAALVM_RELEASE}/graalvm-community-${GRAALVM_JDK}_linux-${arch}_bin.tar.gz"; \
    curl -fsSL -o /tmp/graalvm.tar.gz "$url"; \
    curl -fsSL -o /tmp/graalvm.tar.gz.sha256 "$url.sha256"; \
    echo "$(cat /tmp/graalvm.tar.gz.sha256)  /tmp/graalvm.tar.gz" | sha256sum -c -; \
    mkdir -p /opt/graalvm; \
    tar -xzf /tmp/graalvm.tar.gz -C /opt/graalvm --strip-components=1; \
    rm -f /tmp/graalvm.tar.gz /tmp/graalvm.tar.gz.sha256; \
    /opt/graalvm/bin/java -version
ENV JAVA_HOME=/opt/graalvm \
    PATH=/opt/graalvm/bin:$PATH \
    GRADLE_USER_HOME=/root/.gradle

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# A Gradle init script that resolves every resolvable configuration (runtime classpaths of every source set, the
# JaCoCo agent, ...) so that the dependency cache in /root/.gradle holds everything a later offline test run needs.
RUN mkdir -p /opt/oss-scanner && printf '%s\n' \
      'allprojects { p ->' \
      '    p.tasks.register("ossScannerResolve") {' \
      '        notCompatibleWithConfigurationCache("resolves configurations at execution time")' \
      '        doLast {' \
      '            p.configurations.matching { it.canBeResolved }.each { c ->' \
      '                try { c.files } catch (Throwable t) { println("WARNING: ${p.path}:${c.name}: ${t.message}") }' \
      '            }' \
      '        }' \
      '    }' \
      '}' > /opt/oss-scanner/resolve.gradle

# Build as the maintainers do, minus the tests: download the Gradle wrapper, compile every module (main and test
# sources, with annotation processing), then fetch every runtime dependency. A step that fails fails the build.
RUN ./gradlew --no-daemon --console=plain classes testClasses \
    && ./gradlew --no-daemon --console=plain -I /opt/oss-scanner/resolve.gradle ossScannerResolve

# From here on Gradle must never touch the network. An init script in the Gradle user home turns every later
# invocation into an offline one, so forgetting --offline cannot make a build fail on dynamic/changing versions.
RUN mkdir -p /root/.gradle/init.d && printf '%s\n' \
      '// Added by the OSS Scanner image: the scan runs without a network.' \
      'gradle.startParameter.offline = true' > /root/.gradle/init.d/oss-scanner-offline.gradle

# A cheap test run, to show the image works end to end offline. A failing test does not abort the build.
RUN ./gradlew --no-daemon --console=plain --offline :micronaut-core:test \
    || echo "WARNING: :micronaut-core:test reported failures"

# Micronaut's embedded server advertises $HOSTNAME as its host. In a container without a network the container's
# own hostname is not resolvable, and every test that starts a server and connects to it fails with "Temporary
# failure in name resolution". localhost always resolves. (An ENV here overrides the value Docker injects.)
ENV HOSTNAME=localhost
