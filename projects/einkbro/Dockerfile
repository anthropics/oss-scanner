FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    ANDROID_HOME=/opt/android-sdk
ENV PATH="${ANDROID_HOME}/cmdline-tools/latest/bin:${ANDROID_HOME}/platform-tools:${PATH}"

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip openjdk-17-jdk-headless \
      build-essential python3 nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# Match the project's Java 17, Android 36, pinned NDK and CMake versions.
RUN curl -fsSL -o /tmp/android-tools.zip \
      https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip \
    && echo '7ec965280a073311c339e571cd5de778b9975026cfcbe79f2b1cdcb1e15317ee  /tmp/android-tools.zip' | sha256sum -c - \
    && mkdir -p "$ANDROID_HOME/cmdline-tools" \
    && unzip -q /tmp/android-tools.zip -d "$ANDROID_HOME/cmdline-tools" \
    && mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest" \
    && rm /tmp/android-tools.zip \
    && yes | sdkmanager --licenses > /dev/null \
    && sdkmanager 'platform-tools' 'platforms;android-36' 'build-tools;35.0.0' \
         'ndk;27.0.12077973' 'cmake;3.22.1'

# Keep rebuilds within the scanner's 8 GiB agent environment.
RUN mkdir -p /root/.gradle \
    && printf '%s\n' 'org.gradle.jvmargs=-Xmx4g -Dfile.encoding=UTF-8' \
         'org.gradle.workers.max=2' 'org.gradle.parallel=false' \
         'kotlin.compiler.execution.strategy=in-process' > /root/.gradle/gradle.properties

COPY . /src
WORKDIR /src

# Debug builds need no private signing or Play credentials. Fetch test dependencies
# online as well, so a subsequent audit can rebuild and run tests without a network.
RUN ./gradlew --no-daemon assembleDebug testDebugUnitTest
RUN cd js-tests && npm install --no-audit --no-fund
# The existing translation jsdom suite has failing assertions on main. Keep it
# available to the auditor without preventing a successfully built app from scanning.
RUN cd js-tests && (npm test -- --runInBand || echo 'WARNING: JavaScript tests reported failures')
