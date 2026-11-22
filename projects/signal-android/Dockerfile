# Signal-Android (https://github.com/signalapp/Signal-Android), the Signal messenger for Android.
#
# The toolchain follows reproducible-builds/Dockerfile in the repository (JDK 21, the same command-line tools,
# platform, build tools, NDK and CMake), installed from the public mirrors rather than Signal's apt snapshot. Only
# the playProdDebug variant is built, which is the one CI tests.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip openjdk-21-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

ARG ANDROID_TOOLS=14742923
ARG ANDROID_TOOLS_HASH=04453066b540409d975c676d781da1477479dde3761310f1a7eb92a1dfb15af7
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH="${PATH}:${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools"
RUN curl --proto '=https' --tlsv1.2 -fsSL -o /tmp/tools.zip \
      "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_TOOLS}_latest.zip" \
    && echo "$ANDROID_TOOLS_HASH  /tmp/tools.zip" | sha256sum -c - \
    && mkdir -p "$ANDROID_HOME/cmdline-tools" \
    && unzip -q /tmp/tools.zip -d "$ANDROID_HOME/cmdline-tools" \
    && mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest" \
    && rm /tmp/tools.zip \
    && yes | sdkmanager --licenses > /dev/null \
    && sdkmanager "platform-tools" "platforms;android-37.0" "build-tools;36.0.0" \
      "ndk;28.0.13004108" "cmake;3.22.1" > /dev/null

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the debug app and compile the unit tests of the app and of libsignal-service, which parses what the server and
# other clients send. Resolving every configuration instead would take most of the 45-minute build limit and fetch
# artifacts that gradle/verification-metadata.xml does not list. Running one test class from each suite fetches the
# test runtime, so that the tests work offline during the scan; the app's class runs under Robolectric, which
# downloads its Android framework jar on first use. A failing test does not abort the build.
RUN ./gradlew --no-daemon --console=plain \
      :Signal-Android:assemblePlayProdDebug :Signal-Android:compilePlayProdDebugUnitTestSources \
      :lib:libsignal-service:testClasses
RUN ./gradlew --no-daemon --console=plain --continue \
      :Signal-Android:testPlayProdDebugUnitTest --tests 'org.thoughtcrime.securesms.util.GroupUtilTest' \
      :lib:libsignal-service:test --tests 'org.whispersystems.signalservice.api.crypto.AttachmentCipherTest' \
    || echo "WARNING: the warm-up tests reported failures"

# The scan has no network. This init script makes every later build offline, so that a forgotten --offline cannot
# stall on a repository lookup.
RUN mkdir -p /root/.gradle/init.d \
    && echo 'gradle.startParameter.offline = true' > /root/.gradle/init.d/offline.gradle
