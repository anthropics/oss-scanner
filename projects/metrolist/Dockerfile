# Metrolist (https://github.com/MetrolistGroup/Metrolist), a YouTube Music client for Android.
#
# The build needs JDK 21 (as in CI) and the Android SDK. Only the command-line tools are installed
# here; the Android Gradle Plugin downloads the platform and build tools the project asks for while
# there is a network, once the licences are accepted.
FROM eclipse-temurin:21-jdk-noble
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    ANDROID_HOME=/opt/android-sdk \
    ANDROID_SDK_ROOT=/opt/android-sdk \
    GRADLE_OPTS="-Dorg.gradle.daemon=false"
RUN apt-get update && apt-get install -y --no-install-recommends git unzip curl \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p $ANDROID_HOME/cmdline-tools \
    && curl -fsSL -o /tmp/cmdline-tools.zip \
      https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip \
    && unzip -q /tmp/cmdline-tools.zip -d $ANDROID_HOME/cmdline-tools \
    && mv $ANDROID_HOME/cmdline-tools/cmdline-tools $ANDROID_HOME/cmdline-tools/latest \
    && rm /tmp/cmdline-tools.zip \
    && yes | $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager --licenses >/dev/null \
    && $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager "platform-tools"
ENV PATH=$PATH:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The debug build signs with ~/.android/debug.keystore and its standard passwords, as in CI.
RUN mkdir -p /root/.android && keytool -genkeypair -keystore /root/.android/debug.keystore \
      -storepass android -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 \
      -validity 10000 -dname "CN=Android Debug,O=Android,C=US"

# The default (FOSS) debug APK and every module's unit test classes.
RUN ./gradlew --console=plain assembleFossDebug :app:compileFossDebugUnitTestKotlin \
      :innertube:compileDebugUnitTestKotlin

# Run the unit tests once so the test runtime dependencies land in ~/.gradle. A failing test does
# not abort the build.
RUN ./gradlew --console=plain --continue :app:testFossDebugUnitTest :innertube:testDebugUnitTest \
    || echo "WARNING: the unit tests reported failures"

# The scan has no network: make every later Gradle build offline.
RUN mkdir -p /root/.gradle/init.d \
    && echo 'gradle.startParameter.offline = true' > /root/.gradle/init.d/offline.gradle
