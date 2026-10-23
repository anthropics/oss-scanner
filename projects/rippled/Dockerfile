# OSS Scanner build for rippled / xrpld (https://github.com/XRPLF/rippled): the reference C++ server for
# the XRP Ledger.
#
# This file lives next to project.yaml in the oss-scanner repository. The scanner copies it to
# .oss-scanner/Dockerfile in a fresh clone of rippled's develop branch and builds it with that clone as the
# build context, so `COPY . /src` puts the checkout inside the image. The network is available only while
# this file builds; the scan itself runs offline, so every dependency must be fetched here.
#
# Why Nix rather than apt: rippled is C++23 and needs a bleeding-edge toolchain (CI uses GCC 15 / Clang 23 and
# Conan 2.33, see nix/packages.nix). Those compilers are not packaged by any Debian/Ubuntu release, and
# rippled's own docs say "Linux always builds in a Nix image" (.github/workflows/reusable-build-test-config.yml).
# So instead of approximating the toolchain we build inside one of rippled's own Nix development shells.
#
# Which shell: `.#gcc-plain`, rippled's stock-nixpkgs GCC 15 shell, not the default `.#gcc`. The default shell
# first builds a custom-glibc toolchain from source, which took about 30 minutes on a GitHub runner and 19 on a
# fast laptop, most of the scanner's 45-minute build limit. The plain shell has the same GCC 15, CMake, Ninja,
# Conan and Rust toolchain and realises in a few minutes. It differs from CI only in glibc, which matters for
# the .deb package, not for scanning. Its one cost is handled in the build step below.
#
# Consequence for the scan: binaries built in the dev shell link against glibc/libstdc++ in the Nix store, so
# they must be run from inside the shell. Prefix every run command with `nix develop .#gcc-plain --command`, run from /src
# (threat_model.md spells this out). The dev shell is realised once below while the network is up, so later
# `nix develop` invocations are offline cache hits.
FROM nixos/nix:latest

# rippled's flake needs flakes and the unified nix CLI, both still gated behind experimental-features.
RUN mkdir -p /etc/nix \
    && printf 'experimental-features = nix-command flakes\nmax-jobs = auto\n' >> /etc/nix/nix.conf

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Realise the dev shell once while the network is up. This pulls or builds the pinned toolchain (GCC 15 / Clang 23,
# CMake, Ninja, Conan 2.33, the Rust toolchain from rust-toolchain.toml) into the Nix store, so every later `nix develop` works offline. Its shellHook also runs
# rippled's Conan setup (./conan/init.sh) on entry.
RUN nix develop .#gcc-plain --command true

# Build, mirroring rippled CI (.github/actions/build-deps + reusable-build-test-config.yml):
#   - ./conan/init.sh installs the `ci` Conan profile, global.conf and the xrplf remote
#     (https://conan.xrplf.org/repository/conan/, which carries rippled's patched recipes). Idempotent.
#   - conan install uses --profile:all ci and the host options CI sets: xrpld=True (builds the server). We
#     leave tests off (tests=False): the unit suite is a large share of the compile steps, and the scanner build
#     has 45 minutes. We add assertions=True so the server's XRPL_ASSERT
#     invariant checks are compiled in -- an assert that a peer or transaction can trip is a finding worth
#     catching. build_type=Release keeps the build tractable.
#   - cmake configures with the Conan toolchain and adds -g1 -fno-omit-frame-pointer for debuggable stacks.
#   - cmake --build builds the default targets (the `xrpld` server).
# A step that fails fails the build, and primary_contact gets the log.
# The plain shell sets XRPLD_NO_PATCH_NIX_BINARY, which skips cmake/PatchNixBinary.cmake (it would run a
# `#!/bin/bash` script, and this image has no /bin/bash). The binaries keep their Nix-store loader and run inside
# `nix develop`, as described above.
#
# Conan's prebuilt executables (protoc, the gRPC plugin) are linked against the custom glibc that only the default
# shell builds, so they cannot start here. After `conan install`, point their loader and rpath at this shell's
# glibc and libstdc++ with patchelf. Builds from a newer glibc run fine against older-glibc binaries.
RUN nix develop .#gcc-plain --command bash -eux -o pipefail -c '\
      ./conan/init.sh && \
      mkdir -p .build && cd .build && \
      conan install .. \
        --output-folder . \
        --profile:all ci \
        --build missing \
        --options:host="&:tests=False" \
        --options:host="&:xrpld=True" \
        --options:host="&:assertions=True" \
        --settings:all build_type=Release \
        --conf:all tools.build:jobs="$(nproc)" && \
      libc="$(dirname "$(gcc -print-file-name=libc.so.6)")" && \
      cxx="$(dirname "$(gcc -print-file-name=libstdc++.so.6)")" && \
      ld="$(ls "$libc"/ld-linux-*.so.* | head -1)" && \
      for f in /root/.conan2-nix/p/*/p/bin/*; do \
        if patchelf --print-interpreter "$f" >/dev/null 2>&1; then \
          patchelf --set-interpreter "$ld" --set-rpath "\$ORIGIN/../lib:$libc:$cxx" "$f"; \
        fi; \
      done && \
      cmake \
        -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE:FILEPATH=build/generators/conan_toolchain.cmake \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CXX_FLAGS="-g1 -fno-omit-frame-pointer" \
        -Dxrpld=ON -Dtests=OFF -Dassertions=ON \
        .. && \
      cmake --build . --parallel "$(nproc)"'

# Smoke test, so the log shows the image works: the server binary starts and reports its version.
RUN nix develop .#gcc-plain --command bash -c 'cd /src/.build && ./xrpld --version'

# The scanner adds its own layer on top of this image (Claude Code, analysis tools). The Nix base image has no
# apt/apk and lacks sed, awk and python3, which that layer's installer needs (it already has git, curl, grep and
# bash). It also has no system ELF loader, so the prebuilt `claude` binary cannot start; link the loader from
# Nix's glibc to the standard path. The layer also links claude into /usr/local/bin, which the base image lacks
# and does not have on PATH. Do all of this now while the network is up.
RUN set -e; \
    nix profile install nixpkgs#gnused nixpkgs#gawk nixpkgs#python3; \
    case "$(uname -m)" in \
      x86_64) loader=/lib64/ld-linux-x86-64.so.2 ;; \
      aarch64) loader=/lib/ld-linux-aarch64.so.1 ;; \
      *) echo "unsupported arch: $(uname -m)" >&2; exit 1 ;; \
    esac; \
    glibc="$(nix build --no-link --print-out-paths nixpkgs#glibc.out)"; \
    mkdir -p /usr/local/bin "$(dirname "$loader")"; \
    ln -sf "$glibc/lib/$(basename "$loader")" "$loader"
ENV PATH="/usr/local/bin:${PATH}"
