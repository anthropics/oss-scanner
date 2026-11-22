# sofia-sip, built in-tree at /src with debug info, frame pointers, ASan and UBSan, configured with configure.gnu
# as FreeSWITCH builds it (static, STUN off, no glib; NTH/HTTP on).
#
#   /src/libsofia-sip-ua/.libs/libsofia-sip-ua.a    the library (also installed to /usr/local, pkg-config sofia-sip-ua)
#   /src/libsofia-sip-ua/<module>/                   per-module unit tests and torture_* programs
#   /src/libsofia-sip-ua/sip/test_sip_msg            parses one SIP message from stdin (-t: stream framing)
#   /src/libsofia-sip-ua/sdp/test_sdp                parses one SDP body from stdin or a file
#   /src/tests/check_sofia                           end-to-end NUA/NTA call scenarios (libcheck)
#   /src/utils/sip-options, sip-dig                  command-line SIP and DNS clients
#   /src/make-check.log                              test suite result at image build time
FROM debian:trixie
# -Wno-error=incompatible-pointer-types: GCC 14 rejects a pointer-type mismatch in msg/test_msg.c.
ENV DEBIAN_FRONTEND=noninteractive \
    CFLAGS="-g -O1 -fno-omit-frame-pointer -fsanitize=address,undefined -Wno-error=incompatible-pointer-types" \
    LDFLAGS="-fsanitize=address,undefined" \
    ASAN_OPTIONS=detect_leaks=0:abort_on_error=1:symbolize=1 \
    UBSAN_OPTIONS=print_stacktrace=1 \
    CK_TIMEOUT_MULTIPLIER=5
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential autoconf automake libtool pkg-config git python3 gdb \
      libssl-dev zlib1g-dev check \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN ./autogen.sh \
    && ./configure.gnu \
    && make -j"$(nproc)" \
    && make install

# Build the test programs and run the suite; a failure must not fail the image. -k keeps going past a test
# program that does not build. No DNS server is installed on purpose: the live-DNS cases skip without one.
RUN timeout 1500 make -k -j"$(nproc)" check > /src/make-check.log 2>&1 \
    || { grep -E '^(FAIL|ERROR|# )|\*\*\*' /src/make-check.log | tail -n 80; echo "WARNING: make check reported failures"; }
