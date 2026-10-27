# Build environment for Anthropic's OSS Scanner (https://github.com/anthropics/oss-scanner).
# The scanner builds this with the repository as the build context, then audits the image with no network access.
#
# Clerk is an Apple-platform SDK. ClerkKit imports Security, AuthenticationServices, LocalAuthentication, CryptoKit,
# WatchConnectivity and Darwin's notify, and ClerkKitUI imports SwiftUI, UIKit and AppKit. None of these exist on
# Linux, so the package itself cannot be built here. This image gives the audit the Swift toolchain, the sources and
# every resolved dependency checkout instead. threat_model.md explains how to exercise the platform-independent code.
FROM swift:6.2-bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 ripgrep \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Fetch every package dependency now, while the network is available, into /src/.build/checkouts.
RUN swift package resolve && swift package show-dependencies
