# OSS Scanner build for Clio (https://github.com/XRPLF/clio): an XRP Ledger API server written in C++23.
#
# This file lives next to project.yaml in the oss-scanner repository. The scanner copies it to
# .oss-scanner/Dockerfile in a fresh clone of Clio's develop branch and builds it with that clone as the build
# context. The network is available only while this file builds, so every dependency must be fetched here.
#
# Same approach as the rippled enrollment (projects/rippled/Dockerfile), for the same reasons. Clio is built with
# the same Nix toolchain as xrpld: its flake.nix re-exports xrpld's dev shells, and CI builds in xrpld's Nix image.
# We use the `.#gcc-plain` shell (stock-nixpkgs GCC 15) because the default `.#gcc` shell first builds a custom
# glibc toolchain from source, which takes most of the scanner's build limit. Binaries link against glibc and
# libstdc++ in the Nix store, so run them from inside the shell: prefix commands with
# `nix develop .#gcc-plain --command` from /src (threat_model.md says so).
FROM nixos/nix:latest

RUN mkdir -p /etc/nix \
    && printf 'experimental-features = nix-command flakes\nmax-jobs = auto\n' >> /etc/nix/nix.conf

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Realise the dev shell once while the network is up, so later `nix develop` runs are offline cache hits.
RUN nix develop .#gcc-plain --command true

# Build, mirroring Clio CI (.github/actions/conan and .github/actions/cmake):
#   - ./conan/init.sh installs the `ci` Conan profile, global.conf and the xrplf remote, which carries the prebuilt
#     `xrpl` (libxrpl) package. conan.lock pins versions and is used implicitly.
#   - Tests are off (the unit suite is most of Clio's compile time, and the scanner build has 45 minutes).
#     Release keeps the build tractable; -g1 and frame pointers keep stacks usable, -O1 keeps the compile short.
# The plain shell sets XRPLD_NO_PATCH_NIX_BINARY, which skips cmake/PatchNixBinary.cmake (it needs /bin/bash,
# which this image does not have). Conan's prebuilt tools are linked against the custom glibc of the default shell,
# so point their loader and rpath at this shell's glibc and libstdc++ with patchelf, as the rippled build does.
RUN nix develop .#gcc-plain --command bash -eux -o pipefail -c '\
      ./conan/init.sh && \
      mkdir -p build && \
      conan install . \
        --output-folder build \
        --build missing \
        --profile:all ci \
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
      cmake -S . -B build -G Ninja \
        -DCMAKE_TOOLCHAIN_FILE:FILEPATH=build/generators/conan_toolchain.cmake \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_CXX_FLAGS="-g1 -fno-omit-frame-pointer" \
        -DCMAKE_CXX_FLAGS_RELEASE="-O1 -DNDEBUG" \
        -Dtests=OFF && \
      cmake --build build --parallel "$(nproc)"'

# Smoke test: the server binary starts and prints its version.
RUN nix develop .#gcc-plain --command bash -c 'cd /src/build && ./clio_server --version'

# The scanner adds its own layer (Claude Code, analysis tools). The Nix base image has no apt/apk and lacks sed, awk
# and python3, which that layer's installer needs. It also has no system ELF loader, so the prebuilt `claude` binary
# cannot start, and no /usr/local/bin. Fix all of this now while the network is up (same as the rippled enrollment).
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
