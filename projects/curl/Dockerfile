# Two builds of the same checkout, with ASan/UBSan and debug symbols:
#   /src/build/openssl: OpenSSL, threaded DNS, HTTP/2.
#   /src/build/gnutls:  GnuTLS, c-ares, HTTP/2 and HTTP/3 (ngtcp2/nghttp3).
# Both include the CLI, shared/static libcurl, and regression test binaries.
FROM docker.io/library/debian:trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang-19 \
    CXX=clang++-19 \
    CFLAGS="-g -O1 -fno-omit-frame-pointer -fsanitize=address,undefined" \
    LDFLAGS="-fsanitize=address,undefined" \
    ASAN_OPTIONS=abort_on_error=1:symbolize=1 \
    UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1 \
    ASAN_SYMBOLIZER_PATH=/usr/lib/llvm-19/bin/llvm-symbolizer

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang-19 llvm-19 libclang-rt-19-dev \
      cmake ninja-build pkg-config git perl python3 gdb strace \
      libssl-dev libgnutls28-dev libc-ares-dev libnghttp2-dev \
      libngtcp2-dev libngtcp2-crypto-gnutls-dev libnghttp3-dev \
      libssh2-1-dev libldap-dev libkrb5-dev libgsasl-dev \
      libidn2-dev libpsl-dev zlib1g-dev libbrotli-dev libzstd-dev \
      openssl stunnel4 openssh-client openssh-server openssh-sftp-server \
      nghttp2-server nghttp2-proxy \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the repository is the build context and lives at /src.
COPY . /src
WORKDIR /src

RUN cmake -S /src -B /src/build/openssl -G Ninja \
      -DCMAKE_BUILD_TYPE=Debug -DENABLE_DEBUG=ON \
      -DBUILD_SHARED_LIBS=ON -DBUILD_STATIC_LIBS=ON -DBUILD_TESTING=ON \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DCURL_USE_OPENSSL=ON -DCURL_USE_GNUTLS=OFF \
      -DENABLE_ARES=OFF -DENABLE_THREADED_RESOLVER=ON \
      -DUSE_NGHTTP2=ON -DCURL_USE_LIBSSH2=ON \
      -DCURL_USE_GSSAPI=ON -DCURL_USE_GSASL=ON \
    && cmake --build /src/build/openssl --parallel 2 \
    && cmake --build /src/build/openssl --target testdeps --parallel 2 \
    && /src/build/openssl/src/curl --version

# Trixie's ngtcp2 has the GnuTLS adapter needed for this HTTP/3 build.
RUN cmake -S /src -B /src/build/gnutls -G Ninja \
      -DCMAKE_BUILD_TYPE=Debug -DENABLE_DEBUG=ON \
      -DBUILD_SHARED_LIBS=ON -DBUILD_STATIC_LIBS=ON -DBUILD_TESTING=ON \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DCURL_USE_OPENSSL=OFF -DCURL_USE_GNUTLS=ON \
      -DENABLE_ARES=ON -DENABLE_THREADED_RESOLVER=OFF \
      -DUSE_NGHTTP2=ON -DUSE_NGTCP2=ON -DCURL_USE_LIBSSH2=ON \
      -DCURL_USE_GSSAPI=ON -DCURL_USE_GSASL=ON \
    && cmake --build /src/build/gnutls --parallel 2 \
    && cmake --build /src/build/gnutls --target testdeps --parallel 2 \
    && /src/build/gnutls/src/curl --version

# Exercise the local-server regression suite without aborting image creation
# on a test failure. Logs remain available to the scanner. -n skips Valgrind
# because these binaries already use ASan/UBSan.
RUN for backend in openssl gnutls; do \
      for selection in '1 2 3 4 5 6 7 8 9 10 305 310 500 513 900 901 1000 1001 1002 1003 1700 2400 2407' 'unittest tunittest'; do \
        TFLAGS="-n -j2 --min=1 $selection" \
          timeout 5m cmake --build "/src/build/$backend" --target test-nonflaky \
          >> "/src/build/$backend/smoke-tests.log" 2>&1 \
        || echo "WARNING: $backend smoke tests ($selection) failed or timed out"; \
      done; \
      cat "/src/build/$backend/smoke-tests.log"; \
    done
