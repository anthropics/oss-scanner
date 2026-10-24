# OSS Scanner build for libipuz.
#
# Two builds are produced from the same checkout in /src:
#   /src/build       gcc, debugoptimized, -g -fno-omit-frame-pointer. Mirrors a
#                    distribution build; run the test suite with
#                    `meson test -C /src/build`.
#   /src/build-asan  clang, AddressSanitizer + UndefinedBehaviorSanitizer on the
#                    C code. Use it to confirm memory-safety findings. The Rust
#                    core is not instrumented.
#
# The test programs live in libipuz/tests/ (built into <build>/libipuz/tests/),
# with a corpus of .ipuz files next to them.
FROM registry.fedoraproject.org/fedora:43

RUN dnf -y install \
      gcc clang compiler-rt libasan libubsan llvm \
      git meson ninja-build pkgconf-pkg-config \
      glib2-devel json-glib-devel \
      gettext itstool python3 curl ca-certificates gdb \
    && dnf clean all

# libipuz needs Rust >= 1.92 (libipuz/rust/Cargo.toml); pin it like CI does.
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
RUN curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain 1.92.0

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# 1) Reference build.
RUN meson setup /src/build /src \
      --buildtype=debugoptimized \
      -Dc_args="-g -fno-omit-frame-pointer" \
      -Dintrospection=disabled \
      -Ddocumentation=disabled \
    && meson compile -C /src/build

# 2) Sanitizer build. b_lundef=false is required when linking with -fsanitize=*.
RUN CC=clang meson setup /src/build-asan /src \
      --buildtype=debug \
      -Db_sanitize=address,undefined \
      -Db_lundef=false \
      -Dc_args="-g -fno-omit-frame-pointer -fno-sanitize-recover=undefined" \
      -Dintrospection=disabled \
      -Ddocumentation=disabled \
    && meson compile -C /src/build-asan

ENV ASAN_OPTIONS=detect_leaks=0:abort_on_error=1:symbolize=1 \
    UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1

# Run the tests now: this also makes cargo fetch everything `cargo test` needs,
# since the scan itself runs without network access. Failures are reported but
# do not abort the build.
RUN (meson test -C /src/build --print-errorlogs || echo "WARNING: libipuz tests reported failures") \
 && (meson test -C /src/build-asan --print-errorlogs || echo "WARNING: libipuz ASan tests reported failures")
