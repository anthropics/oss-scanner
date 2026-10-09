# Scanner image for https://github.com/anthropics/buffa.
#
# The audit runs offline, so this build installs the toolchains, fetches every crate, and compiles the tests, the
# conformance binaries and the fuzz targets. threat_model.md, next to this file, says how to run each of them.
# x86-64 only: the protoc download below is the linux-x86_64 release.

# --- The protobuf conformance runner, built the way the repository's conformance/Dockerfile.tools builds it. ---
# It is a separate stage so that the protobuf build tree stays out of the final image.
FROM buildpack-deps:bookworm-scm AS conformance-tools
ENV DEBIAN_FRONTEND=noninteractive
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends cmake g++ make python3 \
    && rm -rf /var/lib/apt/lists/*
# The protobuf and jsoncpp commits are read from the repository's own pins, so that a protobuf bump there reaches
# this image without a change here. The defaults apply only if the pins can no longer be found in that file.
# jsoncpp is built shared because protobuf's conformance build links the jsoncpp_lib target, which only the shared
# build defines; the final image gets the library together with the runner.
COPY conformance/Dockerfile.tools /tmp/Dockerfile.tools
ARG JOBS=8
RUN set -eux; \
    pin() { sed -n "s/^ARG $1=//p" /tmp/Dockerfile.tools | head -n 1; }; \
    jsoncpp="$(pin JSONCPP_COMMIT)"; jsoncpp="${jsoncpp:-89e2973c754a9c02a49974d839779b151e95afd6}"; \
    protobuf="$(pin PROTOBUF_COMMIT)"; protobuf="${protobuf:-b6f9284da830b69be787732ffdaa35049d20a088}"; \
    checkout() { \
        git init -q "$2"; \
        git -C "$2" remote add origin "$1"; \
        git -C "$2" fetch -q --depth=1 origin "$3"; \
        git -C "$2" checkout -q --detach FETCH_HEAD; \
        test "$(git -C "$2" rev-parse HEAD)" = "$3"; \
    }; \
    checkout https://github.com/open-source-parsers/jsoncpp.git /tmp/jsoncpp "$jsoncpp"; \
    cmake -S /tmp/jsoncpp -B /tmp/jsoncpp/_build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=ON \
        -DJSONCPP_WITH_TESTS=OFF -DJSONCPP_WITH_POST_BUILD_UNITTEST=OFF; \
    cmake --build /tmp/jsoncpp/_build -j"$JOBS"; \
    cmake --install /tmp/jsoncpp/_build; \
    checkout https://github.com/protocolbuffers/protobuf.git /protobuf "$protobuf"; \
    cmake -S /protobuf -B /protobuf/_build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
        -Dprotobuf_BUILD_TESTS=OFF -Dprotobuf_BUILD_CONFORMANCE=ON; \
    cmake --build /protobuf/_build --target conformance_test_runner -j"$JOBS"; \
    cp "$(find /protobuf/_build -name conformance_test_runner -type f | head -n 1)" /conformance_test_runner
# The protos that conformance/build.rs and fuzz/build.rs compile, laid out as conformance/protos/ expects.
RUN set -eux; cd /protobuf; \
    mkdir -p /protos/google/protobuf /protos/editions/golden /protos/conformance/test_protos; \
    cp conformance/conformance.proto /protos/; \
    for name in test_messages_proto3 test_messages_proto2 any duration field_mask struct timestamp wrappers; do \
        cp "src/google/protobuf/$name.proto" /protos/google/protobuf/; \
    done; \
    cp editions/golden/test_messages_proto2_editions.proto editions/golden/test_messages_proto3_editions.proto \
        /protos/editions/golden/; \
    cp conformance/test_protos/test_messages_edition2023.proto \
        conformance/test_protos/test_messages_edition_unstable.proto /protos/conformance/test_protos/

# --- The image the scanner works in. ---
# Debian with curl, git and CA certificates. Packages are fetched over HTTPS.
FROM buildpack-deps:bookworm-scm
ENV DEBIAN_FRONTEND=noninteractive \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
# gcc-multilib links the i686 target, so the 32-bit code paths can be run as well as checked.
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
      unzip build-essential clang gcc-multilib pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

# protoc, at the version and checksum that the repository's CI pins (PROTOC_VERSION in .github/workflows/ci.yml).
ARG PROTOC_VERSION=33.5
ARG PROTOC_SHA256=24e58fb231d50306ee28491f33a170301e99540f7e29ca461e0e80fd1239f8d1
RUN curl -fsSL -o /tmp/protoc.zip \
      "https://github.com/protocolbuffers/protobuf/releases/download/v${PROTOC_VERSION}/protoc-${PROTOC_VERSION}-linux-x86_64.zip" \
    && echo "${PROTOC_SHA256}  /tmp/protoc.zip" | sha256sum -c - \
    && unzip -q -o /tmp/protoc.zip 'bin/*' 'include/*' -d /usr/local \
    && rm /tmp/protoc.zip \
    && protoc --version

RUN curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs \
      | sh -s -- -y --profile minimal --default-toolchain none

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src
COPY --from=conformance-tools /conformance_test_runner /usr/local/bin/conformance_test_runner
COPY --from=conformance-tools /usr/local/lib/libjsoncpp.so* /usr/local/lib/
COPY --from=conformance-tools /protos /src/conformance/protos
RUN ldconfig && ! ldd /usr/local/bin/conformance_test_runner | grep 'not found'

# The stable toolchain is the one rust-toolchain.toml pins; it is also made the default, for code written outside /src.
# The i686 and thumbv7em targets are the ones CI checks. The nightly is the one CI pins for Miri (MIRI_TOOLCHAIN in
# ci.yml), and cargo-fuzz needs a nightly as well.
ARG NIGHTLY=nightly-2026-02-27
RUN rustup toolchain install \
    && rustup default "$(rustup show active-toolchain | cut -d' ' -f1)" \
    && rustup target add i686-unknown-linux-gnu thumbv7em-none-eabihf \
    && rustup toolchain install "$NIGHTLY" --profile minimal --component miri,rust-src,llvm-tools \
    && cargo install --locked cargo-fuzz@0.13.2

# An ARG, so that it bounds the memory this build uses without reaching the audit environment.
ARG CARGO_BUILD_JOBS=8

# Every crate that the workspace and the standalone manifests depend on, for all targets.
RUN cargo fetch \
    && for manifest in fuzz/Cargo.toml conformance/Cargo.toml examples/*/Cargo.toml; do \
         cargo fetch --manifest-path "$manifest" || echo "WARNING: could not fetch dependencies of $manifest"; \
       done

# The workspace and its tests, as CI builds them. A step that fails fails the build, and primary_contact gets the log.
RUN cargo test --workspace --no-run

# The conformance binary, with and without std, where conformance/run-conformance.sh expects to find each.
RUN cargo build --release --manifest-path conformance/Cargo.toml \
    && cargo build --release --manifest-path conformance/Cargo.toml --no-default-features \
         --target-dir conformance/target-nostd

# The Miri sysroots for the host and for a 32-bit target.
RUN cargo +"$NIGHTLY" miri setup \
    && cargo +"$NIGHTLY" miri setup --target i686-unknown-linux-gnu

# The fuzz targets, with AddressSanitizer. CI does not build them, so a commit on which they do not compile must not
# fail the whole image; their dependencies are fetched above either way.
RUN cargo +"$NIGHTLY" fuzz build --fuzz-dir fuzz || echo "WARNING: the fuzz targets did not build"

# Run the tests and one conformance suite so the log shows the image works, without letting a failure abort the build.
RUN (timeout 1200 cargo test --workspace || echo "WARNING: cargo test reported failures") \
    && (timeout 600 conformance_test_runner --failure_list conformance/known_failures.txt --maximum_edition 2024 \
          conformance/target/release/conformance || echo "WARNING: the conformance runner reported failures")

# Everything is fetched. From here on cargo must not wait for a registry that it cannot reach.
ENV CARGO_NET_OFFLINE=true
