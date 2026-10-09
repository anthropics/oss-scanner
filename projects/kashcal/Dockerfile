# KashCal: Android app (Kotlin, Gradle) plus two pure-JVM parser modules, icaldav-core and vcard-core.
# Everything the unit tests need (Gradle distribution, Maven dependencies, Android SDK, Robolectric's
# android-all jar) is downloaded here, so the tests run offline afterwards with `./gradlew --offline`.
FROM eclipse-temurin:21-jdk-noble

ENV DEBIAN_FRONTEND=noninteractive \
    ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    GRADLE_USER_HOME=/root/.gradle
ENV PATH=$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip python3 \
    && rm -rf /var/lib/apt/lists/*

# Android command-line tools 23.0, pinned by SHA-1 from Google's repository2-3.xml.
ARG CMDLINE_TOOLS=commandlinetools-linux-16111833_latest.zip
ARG CMDLINE_TOOLS_SHA1=e025545c62a8e64c7559119566a569fb1dec5f60
RUN mkdir -p $ANDROID_HOME/cmdline-tools \
    && curl -fsSL -o /tmp/tools.zip https://dl.google.com/android/repository/$CMDLINE_TOOLS \
    && echo "$CMDLINE_TOOLS_SHA1  /tmp/tools.zip" | sha1sum -c - \
    && unzip -q /tmp/tools.zip -d $ANDROID_HOME/cmdline-tools \
    && mv $ANDROID_HOME/cmdline-tools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest \
    && rm /tmp/tools.zip \
    && yes | sdkmanager --licenses >/dev/null \
    && sdkmanager "platforms;android-37.0" "build-tools;36.0.0" "platform-tools"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src
RUN chmod +x gradlew && echo "sdk.dir=$ANDROID_HOME" > local.properties

# Compile the app and both parser modules with their tests. A compile failure fails the build.
RUN ./gradlew --no-daemon \
      :app:compileDebugUnitTestKotlin :icaldav-core:testClasses :vcard-core:testClasses

# Run the unit tests (the same set CI runs, plus the two modules CI skips). This also downloads
# Robolectric's android-all jar into ~/.m2. A failing test does not abort the build. Tests under
# app/src/test/**/integration/ need live servers and stay excluded unless -Pintegration is passed.
RUN ./gradlew --no-daemon --continue \
      :app:testDebugUnitTest :icaldav-core:test :vcard-core:test \
    || echo "WARNING: some unit tests failed"

# The scanning machine has 2 CPUs and 8 GB, smaller than the project's own defaults (4 GB Gradle
# heap, one test fork per spare core). These user-level settings override gradle.properties.
RUN printf '%s\n' \
      'org.gradle.jvmargs=-Xmx2g -XX:ReservedCodeCacheSize=256m -Dfile.encoding=UTF-8' \
      'kotlin.daemon.jvmargs=-Xmx2g' \
      'org.gradle.workers.max=2' \
      > $GRADLE_USER_HOME/gradle.properties
