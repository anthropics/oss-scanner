# OSS Scanner build for simplex-chat (https://github.com/simplex-chat/simplex-chat).
# Toolchains follow the repository's Dockerfile.build; Haskell build flags follow .github/workflows/build.yml.
# The kotlin stage builds in parallel with the Haskell build and leaves the Android and desktop apps buildable
# offline. The iOS app needs macOS and is not built.
FROM ubuntu:24.04 AS base
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    TZ=Etc/UTC

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y \
      ca-certificates curl git xz-utils unzip build-essential pkg-config cmake patchelf \
      libffi-dev libgmp3-dev libncurses-dev libnuma-dev zlib1g-dev libssl-dev \
      libpq-dev libsqlite3-dev sqlite3 llvm llvm-dev \
    && rm -rf /var/lib/apt/lists/*

# Corretto rather than Ubuntu's OpenJDK, as in Dockerfile.build.
ARG JAVA_VER=17.0.17.10.1
ARG JAVA_HASH_AMD64=e3e11daa5c22a45153bbeff1a0c21bf08631791e4e8d8ed14deba31c7cf9af1a
ARG JAVA_HASH_ARM64=2b460859b681757b33a7591b6238ecaf51569d05d2684984e5f0a89c6514acbc
# hadolint ignore=DL3008
RUN case "$(uname -m)" in \
      x86_64) arch=amd64 hash="$JAVA_HASH_AMD64" ;; \
      aarch64) arch=arm64 hash="$JAVA_HASH_ARM64" ;; \
      *) echo "unsupported architecture $(uname -m)" && exit 1 ;; \
    esac \
    && deb="java-17-amazon-corretto-jdk_$(echo "$JAVA_VER" | sed 's/\.1$/-1/')_$arch.deb" \
    && curl --proto '=https' --tlsv1.2 -fsSL -o "/tmp/$deb" "https://corretto.aws/downloads/resources/$JAVA_VER/$deb" \
    && echo "$hash  /tmp/$deb" | sha256sum -c - \
    && apt-get update && apt-get install -y "/tmp/$deb" \
    && rm -rf "/tmp/$deb" /var/lib/apt/lists/*


FROM base AS kotlin
ARG ANDROID_TOOLS=13114758
ARG ANDROID_TOOLS_HASH=7ec965280a073311c339e571cd5de778b9975026cfcbe79f2b1cdcb1e15317ee
ENV ANDROID_HOME=/opt/android-sdk
RUN curl --proto '=https' --tlsv1.2 -fsSL -o /tmp/tools.zip \
      "https://dl.google.com/android/repository/commandlinetools-linux-${ANDROID_TOOLS}_latest.zip" \
    && echo "$ANDROID_TOOLS_HASH  /tmp/tools.zip" | sha256sum -c - \
    && mkdir -p "$ANDROID_HOME/cmdline-tools" \
    && unzip -q /tmp/tools.zip -d "$ANDROID_HOME/cmdline-tools" \
    && mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest" \
    && rm /tmp/tools.zip \
    && yes | "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" --licenses > /dev/null

# With the default heap, which it takes from Gradle's 2 GB, the Kotlin compiler runs out of memory on :common.
RUN mkdir -p /root/.gradle && echo 'kotlin.daemon.jvmargs=-Xmx4g' > /root/.gradle/gradle.properties

COPY . /src
WORKDIR /src
RUN git submodule update --init --recursive

# Compiling caches only compile classpaths. Resolving every configuration also caches what tests, the google flavor
# and desktop packaging need, so that Gradle works with --offline. Configuring :android installs the SDK platform,
# build tools and NDK it needs.
WORKDIR /src/apps/multiplatform
RUN printf '%s\n' \
      'allprojects {' \
      '    tasks.register("resolveAllDependencies") {' \
      '        def configurations = project.configurations' \
      '        doLast {' \
      '            configurations.findAll { it.canBeResolved }.each { configuration ->' \
      '                configuration.incoming.artifactView { lenient(true) }.files.files' \
      '            }' \
      '        }' \
      '    }' \
      '}' \
      > /tmp/resolve-all.gradle \
    && ./gradlew --no-daemon --init-script /tmp/resolve-all.gradle resolveAllDependencies \
    && rm /tmp/resolve-all.gradle

# The desktop JNI library links libsimplex.so, which is not built here, so its CMake step is skipped.
RUN ./gradlew --no-daemon \
      :common:compileTestKotlinDesktop :desktop:compileKotlinJvm -x cmakeBuildAndCopy \
      :android:compileFossDebugUnitTestKotlin :android:compileGoogleDebugUnitTestKotlin

RUN timeout 600 ./gradlew --no-daemon --offline --continue :common:desktopTest :android:testFossDebugUnitTest \
    || echo "WARNING: Kotlin unit tests reported failures"


FROM base
ENV BOOTSTRAP_HASKELL_NONINTERACTIVE=1 \
    BOOTSTRAP_HASKELL_GHC_VERSION=9.6.3 \
    BOOTSTRAP_HASKELL_CABAL_VERSION=3.10.2.0 \
    BOOTSTRAP_HASKELL_INSTALL_NO_STACK=1 \
    BOOTSTRAP_HASKELL_INSTALL_NO_STACK_HOOK=1 \
    PATH="/root/.cabal/bin:/root/.ghcup/bin:$PATH"
RUN curl --proto '=https' --tlsv1.2 -sSf https://get-ghcup.haskell.org | sh \
    && ghcup set ghc "$BOOTSTRAP_HASKELL_GHC_VERSION" \
    && ghcup set cabal "$BOOTSTRAP_HASKELL_CABAL_VERSION"

COPY . /src
WORKDIR /src
RUN git submodule update --init --recursive

# Flags live in cabal.project.local so that a later `cabal build` or `cabal test` offline reuses this build.
# GHC -j compiles modules in parallel to fit the scanner's 45-minute build limit.
RUN printf '%s\n' \
      'ignore-project: False' \
      'tests: True' \
      'test-show-details: direct' \
      'package direct-sqlcipher' \
      '  flags: +openssl' \
      'package simplexmq' \
      '  ghc-options: -j' \
      'package simplex-chat' \
      '  ghc-options: -j' \
      > cabal.project.local \
    && cabal update \
    && cabal build --jobs="$(nproc)" all

# The full suite takes over an hour; run the fast unit tests, bounded so a hang cannot exhaust the build limit.
RUN timeout 300 "$(cabal list-bin simplex-chat-test)" \
      -m "SimpleX chat protocol" -m "SimpleX chat markdown" -m "JSON Tests" \
    || echo "WARNING: unit tests reported failures"

# Copied last, so that the kotlin stage builds while the Haskell build runs.
ENV ANDROID_HOME=/opt/android-sdk
COPY --from=kotlin /opt/android-sdk /opt/android-sdk
COPY --from=kotlin /root/.gradle /root/.gradle
COPY --from=kotlin /src/apps/multiplatform /src/apps/multiplatform
