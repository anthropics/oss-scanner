# rsyslog build for Anthropic OSS Scanner.
#
# Base: the official rsyslog CI development image (Ubuntu 26.04, clang-21). It
# already contains every library and helper the upstream CI uses (librelp,
# libfastjson, liblognorm, civetweb, OpenSSL, GnuTLS, mbedTLS, ...), so the
# scanner sees the same dependency set as the project's own CI.
#
# Result: one in-tree build at /src with
#   - ASan + UBSan (as in the upstream fuzzing CI lanes; unsigned-integer-overflow
#     is left out because intentional hash wrap-around would only add noise),
#   - the broad module set of the CI image (all network inputs, parsers,
#     message modification modules, TLS drivers, outputs),
#   - the testbench (tests/, imdiag, tcpflood, ...), and
#   - the libFuzzer targets tools/fuzz_rsyslog_message and
#     tools/fuzz_imtcp_session (--enable-fuzzing).
FROM docker.io/rsyslog/rsyslog_dev_base_ubuntu:26.04

ENV CC=clang-21 \
    CFLAGS="-g -O1 -fno-omit-frame-pointer -fstack-protector -D_FORTIFY_SOURCE=2 -fsanitize=fuzzer-no-link,address,undefined -fno-sanitize-recover=undefined -fno-sanitize=function -fno-color-diagnostics" \
    LDFLAGS="-fsanitize=address,undefined -fno-sanitize=function" \
    RSYSLOG_CONFIGURE_OPTIONS_EXTRA="--enable-debug --enable-fuzzing --enable-imbeats --enable-imdtls --enable-omdtls --enable-omotel --enable-mmsnareparse --disable-elasticsearch-tests --disable-kafka-tests --disable-libfaketime --without-valgrind-testbench --disable-valgrind" \
    ASAN_OPTIONS="detect_leaks=0:abort_on_error=1:symbolize=1" \
    UBSAN_OPTIONS="print_stacktrace=1:halt_on_error=1" \
    LSAN_OPTIONS="detect_leaks=0" \
    RSYSLOG_TESTBENCH_SKIP_SERVICE_RELEVANCE=1

# Scanner contract: the repository is the build context and lives at /src.
# The base image runs as the unprivileged "rsyslog" user (passwordless sudo),
# which is also how the upstream testbench is run in CI.
USER root
COPY --chown=rsyslog:rsyslog . /src
USER rsyslog
WORKDIR /src

# Same configure entry point as upstream CI (devtools/run-configure.sh uses the
# image's RSYSLOG_CONFIGURE_OPTIONS plus the EXTRA options above).
RUN devtools/run-configure.sh \
    && make -j"$(nproc)" \
    && ./tools/rsyslogd -v

# Build the testbench helpers without running the whole suite.
RUN make -j"$(nproc)" check TESTS=""

# Smoke tests: network inputs, parsers, TLS, and both fuzz targets. A failing
# test must not abort the image build; tests/*.log keeps the details.
# RSYSLOG_TESTBENCH_SKIP_SERVICE_RELEVANCE=1 (above) turns off the PR-CI
# relevance gate, which would otherwise skip e.g. the imbeats tests here.
RUN make check -j2 TESTS=" \
      imtcp-basic.sh imtcp_conndrop.sh imudp_thread_hang.sh imptcp-basic-hup.sh \
      imrelp-basic.sh sndrcv_relp.sh imhttp-post-payload.sh imbeats-basic.sh \
      imdtls-basic.sh sndrcv_tls_anon_ipv4.sh sndrcv_tls_ossl_anon_ipv4.sh \
      rfc5424parser.sh pmrfc3164-msgFirstSpace.sh mmjsonparse_simple.sh \
      imuxsock_logger.sh fuzz-syslog-message-smoke.sh fuzz-imtcp-session-smoke.sh" \
    || (echo "WARNING: rsyslog smoke tests reported failures"; cat tests/test-suite.log || true)
