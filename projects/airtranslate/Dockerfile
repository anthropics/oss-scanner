# AirTranslate is a macOS-only SwiftPM app (AppKit, SwiftUI, ScreenCaptureKit, Speech, Translation; macOS 26+).
# The package requires Swift 6.2. The scanner builds on Linux, so the full app target cannot compile here.
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

# Build the platform-independent core library with debug info. A failure must fail the image build so the
# scanner can report it to primary_contact rather than silently accepting an unbuilt project.
RUN swift build --target AirTranslateCore -c debug -Xswiftc -g

# Python unit tests for latency trace tooling run on Linux and must pass before the image is accepted.
RUN python3 -m unittest discover -s script/tests -v
