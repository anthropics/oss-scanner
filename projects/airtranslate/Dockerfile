# AirTranslate is a macOS-only SwiftPM app (AppKit, SwiftUI, ScreenCaptureKit, Speech, Translation; macOS 26+,
# Xcode 27 / Swift 6.4 for the full app). The scanner builds on Linux, so the full app target cannot compile here.
# This image provides the full source at /src plus a Linux Swift toolchain, and builds the Foundation-only
# AirTranslateCore library target so the agent can compile and exercise that part. The app target and the
# macOS-only test suite are reviewed as source.
FROM swift:6.2-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the platform-independent core library with debug info. Do not fail the image if the Linux toolchain
# rejects the package manifest (it declares macOS-only frameworks for the app target).
RUN (swift build --target AirTranslateCore -c debug -Xswiftc -g \
      || echo "WARNING: AirTranslateCore did not build on Linux; source remains at /src for review")

# Python unit tests for latency trace tooling run on Linux.
RUN (python3 -m unittest discover -s script/tests -v || echo "WARNING: script/tests reported failures")
