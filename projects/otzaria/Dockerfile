# Otzaria is a Flutter app. Its search engine and OpenType shaper are Rust libraries
# delivered by Dart build hooks, which download a published binary or compile it with cargo.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git unzip xz-utils zip file python3 \
      build-essential clang cmake ninja-build pkg-config \
      libgtk-3-dev libsqlite3-dev libzstd1 libglu1-mesa \
    && rm -rf /var/lib/apt/lists/*

# The Flutter version CI pins (.github/workflows/flutter_tests.yml).
ARG FLUTTER_VERSION=3.47.2
RUN git clone --depth 1 --branch "$FLUTTER_VERSION" https://github.com/flutter/flutter.git /opt/flutter
ENV PATH="/opt/flutter/bin:/opt/flutter/bin/cache/dart-sdk/bin:/root/.cargo/bin:${PATH}" \
    FLUTTER_SUPPRESS_ANALYTICS=true \
    CI=true
RUN flutter config --no-analytics --no-cli-animations && flutter precache --linux

# Needed only when a pinned engine has no published binary; the hook then builds from source.
RUN curl -fsSL https://sh.rustup.rs | sh -s -- -y --profile minimal

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every dependency now; the audit runs offline.
RUN flutter pub get --enforce-lockfile \
    && (cd packages/otzaria_report_contract && dart pub get)

# The first `dart run` runs the native build hooks (search engine, shaper) and the generators tests rely on.
RUN dart run tool/generate_search_index.dart \
    && dart run tool/generate_settings_l10n.dart

# The zstd dictionary the codec tests use, pinned as in CI.
RUN set -eu; \
    base="https://raw.githubusercontent.com/Otzaria/SeforimLibrary/cdc5a50fc5c831284e190ad15791b72af8198a57/generator/common/src"; \
    mkdir -p build/test_fixtures; \
    curl -fsSL --retry 3 -o build/test_fixtures/line_content.zdict "$base/jvmMain/resources/zstd/line_content.zdict"; \
    echo "7b08b7c3534c9f9cd0e8f18414b4326aeeb64cfd574cc0f12d83b6f92bd6a396  build/test_fixtures/line_content.zdict" | sha256sum -c -

# The Linux desktop build needs our patched WPE WebKit SDK, so the image stops at the tests.
# A cheap test run so we know the image works; failures do not abort the build.
# Two app_paths tests fail as root, which can write to the read-only folders they create.
RUN (flutter test --no-pub test/core test/utils || echo "WARNING: flutter test reported failures")
