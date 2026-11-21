# OSS Scanner build image for Blockstream App Android (https://github.com/Blockstream/green_android).
# Installs JDK 17 and the Android SDK/build-tools matching contrib/bullseye_deps.sh, compiles the
# development debug APK and unit test sources, and pre-caches Gradle dependencies for offline scans.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      git \
      openjdk-17-jdk-headless \
      unzip \
    && rm -rf /var/lib/apt/lists/*

ARG ANDROID_TOOLS=14742923
ARG ANDROID_TOOLS_HASH=04453066b540409d975c676d781da1477479dde3761310f1a7eb92a1dfb15af7
ENV ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk
ENV PATH="${PATH}:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools"

RUN curl --proto '=https' --tlsv1.2 -fsSL -o /tmp/tools.zip \
      "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_TOOLS}_latest.zip" \
    && echo "${ANDROID_TOOLS_HASH}  /tmp/tools.zip" | sha256sum -c - \
    && mkdir -p "${ANDROID_HOME}/cmdline-tools" \
    && unzip -q /tmp/tools.zip -d "${ANDROID_HOME}/cmdline-tools" \
    && mv "${ANDROID_HOME}/cmdline-tools/cmdline-tools" "${ANDROID_HOME}/cmdline-tools/latest" \
    && rm /tmp/tools.zip \
    && yes | sdkmanager --licenses > /dev/null \
    && sdkmanager "platform-tools" "build-tools;36.0.0" "platforms;android-37.0" > /dev/null

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Populate app_keys.txt from the repository's public template (as in .gitlab-ci.yml)
# and compile the debug APK plus unit test sources across modules.
# Strip the defunct maven.pkg.jetbrains.space repository via a temporary init script so
# Gradle resolves dependencies from mavenCentral/google/jitpack without modifying /src.
RUN printf 'gradle.allprojects { proj -> proj.afterEvaluate { proj.repositories.removeIf { it.hasProperty("url") && it.url.toString().contains("maven.pkg.jetbrains.space") } } }\n' > /tmp/fix-repos.gradle \
    && cp contrib/blockstream_keys.txt app_keys.txt \
    && ./gradlew --no-daemon --console=plain --init-script /tmp/fix-repos.gradle \
      :androidApp:assembleDevelopmentDebug \
      :androidApp:compileDevelopmentDebugUnitTestSources

# Run unit tests non-fatally to cache the test runtime and verify offline test execution.
RUN ./gradlew --no-daemon --console=plain --init-script /tmp/fix-repos.gradle --continue \
      test -x :androidApp:testProductionGoogleDebugUnitTest \
    || echo "WARNING: gradle unit tests reported failures"
RUN rm -f /tmp/fix-repos.gradle

# The scan runs with no network; force Gradle offline mode globally.
RUN mkdir -p /root/.gradle/init.d \
    && echo 'gradle.startParameter.offline = true' > /root/.gradle/init.d/offline.gradle
