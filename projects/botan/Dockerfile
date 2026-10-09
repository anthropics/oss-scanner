# OSS Scanner build for Botan (https://github.com/randombit/botan).
#
# This file lives next to project.yaml in the oss-scanner repository. The scanner copies it to .oss-scanner/Dockerfile
# in a fresh clone of Botan's master branch and builds it with that clone as the context. The network is available
# only while this file builds; the scan itself runs offline.
#
# Two trees are built. They follow Botan's own CI targets in src/scripts/ci_build.py ("sanitizer" and "valgrind"), minus
# the parts that need Go and BoringSSL's BoGo runner:
#
#   /src/build-asan   clang, ASan + UBSan + libstdc++ debug iterators, -O1 -g: static library, `botan` CLI, `botan-test`,
#                     and every src/fuzzer harness as a standalone binary in build-asan/build/fuzzer/ that reads the files
#                     named on its command line (or stdin) and exits.
#   /src/build-dbg    clang, -O3 -g with frame pointers, valgrind client requests for the constant-time checks: shared and
#                     static library, `botan` CLI, `botan-test`, `botan_ct_selftest`. Installed to /usr/local so the Python
#                     binding (src/python/botan3.py) and FFI users find libbotan-3.so.
#
# Neither tree is configured with --unsafe-fuzzer-mode. That flag disables signature and MAC checks so that fuzzers can
# reach deeper; a scan built that way would report "bypasses" that do not exist in a real build.
FROM ubuntu:24.04
# ccache keeps compiled objects in a BuildKit cache mount (see the two build steps), so a rebuild on the same Docker host
# recompiles only what changed. The first build pays a few percent to fill it; a fresh host simply misses and compiles.
# `RUN --mount` needs BuildKit, the default builder since Docker 23 and what tools/check uses; if a builder ever rejects
# it, drop the two --mount lines and the --compiler-cache flags and nothing else changes.
ENV DEBIAN_FRONTEND=noninteractive CCACHE_DIR=/root/.cache/ccache CCACHE_MAXSIZE=10G

# clang is clang-18 on this release; libclang-rt-18-dev holds its sanitizer runtimes. valgrind supplies the
# valgrind/memcheck.h header that --with-valgrind needs, and gdb is used by src/scripts/test_fuzzers.py --gdb.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 make ccache clang libclang-rt-18-dev \
      libboost-dev libbz2-dev liblzma-dev libsqlite3-dev zlib1g-dev \
      gdb valgrind \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Tree 1: sanitizers. The generated Makefile names sources relative to the checkout, so make runs from /src with -f.
#  --with-debug-asserts            enables the BOTAN_DEBUG_ASSERT checks that release builds compile out
#  --unsafe-terminate-on-asserts   a failed BOTAN_ASSERT aborts, so it shows up like a crash; a normal build throws
#                                  Botan::Internal_Error instead (threat_model.md explains how to rate these)
#  --disable-modules=locking_allocator  secure_vector memory then comes from malloc, where ASan sees every allocation,
#                                  rather than from the mlock()ed pool that would hide overflows between neighbours
#  --enable-experimental-features  builds the experimental modules (ffi_tls, ...) too, as CI does
RUN --mount=type=cache,target=/root/.cache/ccache \
    python3 ./configure.py --cc=clang --compiler-cache=ccache --with-build-dir=/src/build-asan \
      --build-targets=static,cli,tests --build-fuzzers=test \
      --with-debug-info --with-debug-asserts --unsafe-terminate-on-asserts \
      --enable-sanitizers=address,undefined,iterator \
      --disable-modules=locking_allocator --enable-experimental-features --without-documentation \
      --with-zlib --with-bzip2 --with-lzma --with-sqlite3 --with-boost \
    && make -f /src/build-asan/Makefile -j"$(nproc)" && ccache -s

# Tree 2: optimized, with debug info and frame pointers, shared library, valgrind annotations for the CT self-test.
RUN --mount=type=cache,target=/root/.cache/ccache \
    python3 ./configure.py --cc=clang --compiler-cache=ccache --with-build-dir=/src/build-dbg --prefix=/usr/local \
      --build-targets=shared,static,cli,tests,ct_selftest \
      --with-debug-info --extra-cxxflags=-fno-omit-frame-pointer --with-valgrind \
      --disable-modules=locking_allocator --enable-experimental-features --without-documentation \
      --with-zlib --with-bzip2 --with-lzma --with-sqlite3 --with-boost \
    && make -f /src/build-dbg/Makefile -j"$(nproc)" && ccache -s \
    && make -f /src/build-dbg/Makefile install && ldconfig

# Seed inputs for the fuzzer binaries: /src/fuzzer_corpus/<name>/ matches build-asan/build/fuzzer/<name>.
RUN git clone --quiet --depth=1 https://github.com/randombit/crypto-corpus.git /src/fuzzer_corpus

# Smoke tests, so the log shows whether the image works. botan-test runs a short, explicit sample of suites (symmetric
# ciphers, AEADs, hashes, signatures, KEMs, RNGs, ASN.1, TLS messages) rather than the whole suite minus a skip list: new
# expensive suites then cannot creep into the build budget. botan-test ignores names it no longer knows, so a renamed
# suite drops out silently; glance at this list now and then. Each step is capped and failures are printed but never fail
# the build. The full suite, the CLI test scripts and the valgrind runs are left for the scan (threat_model.md says how).
# LeakSanitizer needs ptrace, which `docker build` does not grant, so leak detection is off in this step only.
RUN (ASAN_OPTIONS=detect_leaks=0 timeout 3m ./build-asan/botan-test --test-threads="$(nproc)" \
       aead block_ciphers cipher_modes stream_ciphers hash_algos ecdsa_sign ecdsa_verify rsa_sign rsa_verify ecdh_kat ml_kem_kat hmac_drbg auto_rng_unit asn1_decoding asn1_encoding base64 tls_messages tls_policy \
       || echo "WARNING: botan-test (ASan tree) reported failures or ran out of time") \
    && (ASAN_OPTIONS=detect_leaks=0 timeout 4m python3 src/scripts/test_fuzzers.py fuzzer_corpus build-asan/build/fuzzer \
       || echo "WARNING: test_fuzzers.py reported crashes or ran out of time") \
    && (PYTHONPATH=/src/src/python timeout 2m python3 -b src/scripts/test_python.py \
       || echo "WARNING: test_python.py reported failures or ran out of time")
