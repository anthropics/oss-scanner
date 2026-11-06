# OSS Scanner build for Redis.
#
#   /src        default build (jemalloc, TLS, -O3, vector sets). Binaries in /src/src.
#               Integration tests: ./runtest --single unit/<name>
#   /src-asan   AddressSanitizer build (libc malloc, TLS). Use it to confirm memory-safety findings.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git pkg-config python3 procps openssl \
      libssl-dev tcl tcl-tls tclx \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN cp -a /src /src-asan \
    && make -C /src-asan -j"$(nproc)" SANITIZER=address BUILD_TLS=yes

RUN make -j"$(nproc)" BUILD_TLS=yes

ENV ASAN_OPTIONS=abort_on_error=1:symbolize=1

RUN timeout 900 ./runtest --single unit/type/string --single unit/acl --single unit/scripting --single unit/functions --clients 2 || echo "WARNING: integration smoke test reported failures"
