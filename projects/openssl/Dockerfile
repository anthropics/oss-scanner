# OSS Scanner build of OpenSSL (master).
#
# What is built:
#   /src         in-tree debug build with AddressSanitizer + UBSan, all optional
#                algorithms/protocols enabled and the FIPS provider. libcrypto,
#                libssl, providers and the openssl app; `make test` works here.
#                Includes fuzz/<name>-test, which replay inputs through the
#                fuzz harnesses (no libFuzzer; OSS-Fuzz does the fuzzing).
#
# Debian trixie for clang 19: older clang ASan runtimes crash on hosts with
# vm.mmap_rnd_bits > 28, which we cannot change inside a container build.
FROM docker.io/library/debian:trixie
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang-19 \
    CXX=clang++-19 \
    ASAN_OPTIONS=detect_leaks=0:abort_on_error=1:symbolize=1 \
    UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1 \
    ASAN_SYMBOLIZER_PATH=/usr/lib/llvm-19/bin/llvm-symbolizer

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang-19 llvm-19 libclang-rt-19-dev \
      perl make git python3 gdb less \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN ./Configure --banner=Configured --debug \
      enable-asan enable-ubsan -fno-omit-frame-pointer \
      enable-fips enable-lms enable-ec_explicit_curves enable-ec_nistp_64_gcc_128 \
      enable-rc5 enable-md2 enable-weak-ssl-ciphers enable-nextprotoneg enable-ssl-trace \
    && make -s -j"$(nproc)" \
    && ./util/opensslwrap.sh version -a

# Smoke tests, including replay of the fuzz corpora through the sanitized
# library. A failing test must not abort the build. Run the full suite inside
# the image with: cd /src && make test HARNESS_JOBS=2
RUN make test HARNESS_JOBS="$(nproc)" TESTS='test_fuzz* test_evp test_ssl_new test_x509 test_verify' \
    || echo "WARNING: make test reported failures"
