# OSS Scanner build for libsoup (https://gitlab.gnome.org/GNOME/libsoup).
#
# libsoup is GNOME's HTTP client/server library. This image is Fedora 44 with the packages from upstream CI
# (.gitlab-ci.yml), and the fuzzers follow google/oss-fuzz's projects/libsoup. Three trees:
#
#   /src/build       gcc, debugoptimized, every optional feature, examples and the full test suite,
#                    including the Apache-backed auth/connection/proxy tests and NTLM through ntlm_auth.
#   /src/build-asan  clang, ASan + UBSan, examples and the test suite. NTLM is disabled, as in upstream's
#                    fedora-asan job.
#   /src/build-fuzz  clang, ASan + UBSan, a static libsoup with coverage instrumentation and the libFuzzer
#                    targets from fuzzing/.
FROM fedora:44

RUN dnf install -y --setopt=install_weak_deps=False \
      gcc clang compiler-rt llvm meson ninja-build pkgconf-pkg-config git python3 which \
      glib2-devel glib-networking gnutls-devel libnghttp2-devel libpsl-devel sqlite-devel \
      brotli-devel libzstd-devel krb5-devel zlib-ng-compat-devel \
      httpd mod_ssl mod_http2 samba-winbind-clients \
      gdb valgrind strace lsof procps-ng curl nghttp2 openssl socat \
    && dnf clean all

COPY . /src
WORKDIR /src

ARG COMMON="--wrap-mode=nofallback --auto-features=enabled -Dautobahn=disabled \
  -Dintrospection=disabled -Dvapi=disabled -Ddocs=disabled -Dsysprof=disabled"

# 1) Reference build.
RUN meson setup /src/build /src $COMMON \
      --buildtype=debugoptimized \
      -Dc_args="-fno-omit-frame-pointer" \
    && meson compile -C /src/build

# 2) Sanitizer build of the library, examples and tests. -fsanitize=function is off because GObject code calls
#    callbacks through cast function pointers (G_CALLBACK, GDestroyNotify) by design.
RUN CC=clang meson setup /src/build-asan /src $COMMON \
      --buildtype=debug \
      -Db_sanitize=address,undefined -Db_lundef=false \
      -Dc_args="-fno-sanitize=function" \
      -Dntlm=disabled \
    && meson compile -C /src/build-asan

# 3) libFuzzer build, with the library itself instrumented for coverage (as OSS-Fuzz does). The sanitizers are in
#    c_args/c_link_args rather than b_sanitize so that Meson's compile-and-link checks see the coverage runtime.
RUN CC=clang meson setup /src/build-fuzz /src $COMMON \
      -Doptimization=1 \
      --default-library=static \
      -Dc_args="-fsanitize=address,undefined,fuzzer-no-link -fno-sanitize=function -fno-sanitize-recover=undefined" \
      -Dc_link_args="-fsanitize=address,undefined" \
      -Dtests=false -Dtls_check=false -Dfuzzing=enabled \
    && meson compile -C /src/build-fuzz

ENV ASAN_OPTIONS=abort_on_error=1 \
    UBSAN_OPTIONS=halt_on_error=1:print_stacktrace=1 \
    LSAN_OPTIONS=suppressions=/src/.gitlab-ci/leak_suppressions \
    SOUP_TEST_NO_IPV6=1

# Run the test suites so their logs are in the image, but do not let a failing test abort the build. The fuzzing
# suite is fuzzing/meson.build's short run of each fuzzer (200,000 inputs, with its dictionary and seeds).
RUN cd /src/build-fuzz \
    && (timeout 10m meson test --no-rebuild --print-errorlogs --suite fuzzing \
        || echo "WARNING: libsoup fuzzers reported failures; see /src/build-fuzz/meson-logs/testlog.txt")

RUN cd /src/build \
    && (timeout 15m meson test --no-rebuild --print-errorlogs \
        || echo "WARNING: libsoup tests reported failures; see /src/build/meson-logs/testlog.txt")

RUN cd /src/build-asan \
    && (ASAN_OPTIONS=abort_on_error=1:fast_unwind_on_malloc=0 \
          timeout 15m meson test --no-rebuild --print-errorlogs --timeout-multiplier 3 \
        || echo "WARNING: libsoup ASan tests reported failures; see /src/build-asan/meson-logs/testlog.txt")
