# OSS Scanner build of wolfSSL (https://github.com/wolfSSL/wolfssl, master).
#
# The scanner copies this file to .oss-scanner/Dockerfile in a fresh clone of wolfSSL and builds it with that
# clone as the context. The network is available only while this file builds; the scan that follows runs
# offline on a small machine (2 CPUs, 8 GB), so everything an agent might need is fetched or built here.
#
# What is built (threat_model.md says how to use each):
#
#   /src                  in-tree debug build, clang with AddressSanitizer + UndefinedBehaviorSanitizer,
#                         configured with --enable-all --enable-sniffer: TLS 1.2/1.3, DTLS 1.2/1.3, QUIC, ECH,
#                         early data, session tickets, OCSP/CRL, the OpenSSL compatibility layer, PKCS#7/CMS,
#                         ML-KEM and the rest, plus the post-quantum signatures --enable-all leaves out (ML-DSA,
#                         SLH-DSA, LMS, XMSS). Gives libwolfssl, examples/client/client,
#                         examples/server/server, tests/unit.test, testsuite/testsuite.test,
#                         wolfcrypt/test/testwolfcrypt and sslSniffer/sslSnifferTest/snifftest.
#                         Installed to /usr/local.
#   /opt/wolfssl-default  the same commit with a plain `./configure` (wolfSSL's default feature set) and the
#                         same sanitizers. Sources and build tree in /opt/wolfssl-default/src, installed to
#                         /opt/wolfssl-default. Use it to check whether a defect is reachable in a default build.
#
# Also installed: tlslite-ng and tlsfuzzer in /opt/tlsfuzzer (for crafting TLS records and handshakes against
# examples/server), and the openssl CLI (interop, minting test certificates).
#
# Debian trixie for clang 19: older clang ASan runtimes crash on hosts with vm.mmap_rnd_bits > 28.
FROM docker.io/library/debian:trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++ \
    SAN_FLAGS="-g -O1 -fno-omit-frame-pointer -fsanitize=address,undefined -fno-sanitize=function" \
    ASAN_OPTIONS=detect_leaks=0:abort_on_error=1:symbolize=1 \
    UBSAN_OPTIONS=print_stacktrace=1 \
    ASAN_SYMBOLIZER_PATH=/usr/lib/llvm-19/bin/llvm-symbolizer

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang-19 llvm-19 libclang-rt-19-dev \
      autoconf automake libtool pkg-config make git python3 python3-venv \
      libpcap-dev openssl gdb valgrind strace less \
    && ln -sf /usr/bin/clang-19 /usr/local/bin/clang \
    && ln -sf /usr/bin/clang++-19 /usr/local/bin/clang++ \
    && ln -sf /usr/bin/llvm-symbolizer-19 /usr/local/bin/llvm-symbolizer \
    && rm -rf /var/lib/apt/lists/*

# tlslite-ng and tlsfuzzer from git (tlsfuzzer tracks tlslite-ng master). Run tlsfuzzer scripts with
# `tlsfuzzer-python /opt/tlsfuzzer/tlsfuzzer/scripts/<script>.py -h localhost -p <port>`.
RUN git clone --quiet --depth 1 https://github.com/tlsfuzzer/tlslite-ng /opt/tlsfuzzer/tlslite-ng \
    && git clone --quiet --depth 1 https://github.com/tlsfuzzer/tlsfuzzer /opt/tlsfuzzer/tlsfuzzer \
    && python3 -m venv /opt/tlsfuzzer/venv \
    && /opt/tlsfuzzer/venv/bin/pip install --quiet /opt/tlsfuzzer/tlslite-ng ecdsa \
    && printf '#!/bin/sh\nPYTHONPATH=/opt/tlsfuzzer/tlsfuzzer${PYTHONPATH:+:$PYTHONPATH} exec /opt/tlsfuzzer/venv/bin/python "$@"\n' \
        > /usr/local/bin/tlsfuzzer-python \
    && chmod 0755 /usr/local/bin/tlsfuzzer-python \
    && tlsfuzzer-python -c "import tlslite, tlsfuzzer.runner"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Generate configure once, then take a pristine copy of the tree for the default build before /src is
# configured in-tree.
RUN ./autogen.sh \
    && mkdir -p /opt/wolfssl-default/src \
    && tar -C /src --exclude=./.git -cf - . | tar -C /opt/wolfssl-default/src -xf -

# Tree 1, /src: everything on, debug logging available (wolfSSL_Debugging_ON()), sanitizers. A failing step
# here fails the image, and primary_contact gets the log.
RUN ./configure --enable-all --enable-sniffer --enable-debug \
      --enable-mldsa --enable-slhdsa --enable-lms --enable-xmss \
      CFLAGS="$SAN_FLAGS" LDFLAGS="-fsanitize=address,undefined" \
    && make -j"$(nproc)" \
    && make install && ldconfig \
    && ls -l /usr/local/lib/libwolfssl.so

# Tree 2, /opt/wolfssl-default: the default feature set, same sanitizers, no debug logging.
RUN cd /opt/wolfssl-default/src \
    && ./configure --prefix=/opt/wolfssl-default \
      CFLAGS="$SAN_FLAGS" LDFLAGS="-fsanitize=address,undefined" \
    && make -j"$(nproc)" \
    && make install

# Smoke tests, so the log shows whether the image works. Each step is capped, and a failure is printed but never
# fails the build. The full suite (`make check`, or `./tests/unit.test` alone) is left for the scan.
RUN (timeout 10m ./wolfcrypt/test/testwolfcrypt > /tmp/testwolfcrypt.log 2>&1 \
       && echo "testwolfcrypt passed" \
       || { tail -n 40 /tmp/testwolfcrypt.log; echo "WARNING: testwolfcrypt reported failures or ran out of time"; }) \
    && (timeout 10m ./testsuite/testsuite.test > /tmp/testsuite.log 2>&1 \
       && echo "testsuite passed" \
       || { tail -n 40 /tmp/testsuite.log; echo "WARNING: testsuite reported failures or ran out of time"; }) \
    && (cd /opt/wolfssl-default/src && timeout 10m ./testsuite/testsuite.test > /tmp/testsuite-default.log 2>&1 \
       && echo "testsuite (default build) passed" \
       || { tail -n 40 /tmp/testsuite-default.log; echo "WARNING: default-build testsuite reported failures or ran out of time"; })

# Final assertion against the finished image: fail the build if what the agent actually gets is broken.
RUN set -eu; \
    fail() { echo "ENVIRONMENT ASSERTION FAILED: $*" >&2; exit 1; }; \
    for bin in examples/client/client examples/server/server tests/unit.test testsuite/testsuite.test \
               wolfcrypt/test/testwolfcrypt sslSniffer/sslSnifferTest/snifftest; do \
        [ -x "/src/$bin" ] || fail "/src/$bin is missing"; \
    done; \
    for macro in WOLFSSL_HAVE_MLDSA WOLFSSL_HAVE_SLHDSA WOLFSSL_HAVE_LMS WOLFSSL_HAVE_XMSS; do \
        grep -qw "#define $macro" /usr/local/include/wolfssl/options.h || fail "$macro is not set in the /src build"; \
    done; \
    printf '%s\n' '#include <wolfssl/options.h>' '#include <wolfssl/ssl.h>' \
        'int main(void) {' \
        '    WOLFSSL_CTX* ctx;' \
        '    if (wolfSSL_Init() != WOLFSSL_SUCCESS) return 1;' \
        '    ctx = wolfSSL_CTX_new(wolfSSLv23_client_method());' \
        '    if (ctx == NULL) return 2;' \
        '    wolfSSL_CTX_free(ctx);' \
        '    return wolfSSL_Cleanup() == WOLFSSL_SUCCESS ? 0 : 3;' \
        '}' > /tmp/poc.c; \
    clang $SAN_FLAGS /tmp/poc.c -o /tmp/poc -lwolfssl && /tmp/poc \
        || fail "cannot build and run a program against /usr/local (the --enable-all build)"; \
    clang $SAN_FLAGS -I/opt/wolfssl-default/include /tmp/poc.c -o /tmp/poc \
        -L/opt/wolfssl-default/lib -Wl,-rpath,/opt/wolfssl-default/lib -lwolfssl && /tmp/poc \
        || fail "cannot build and run a program against /opt/wolfssl-default"; \
    rm -f /tmp/poc /tmp/poc.c; \
    tlsfuzzer-python -c "import tlslite, tlsfuzzer.runner" || fail "tlsfuzzer-python cannot import tlsfuzzer"; \
    echo "all environment assertions passed"
