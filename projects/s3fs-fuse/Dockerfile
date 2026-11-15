# OSS Scanner build for s3fs-fuse, a FUSE file system that mounts an Amazon S3 bucket,
# or any S3-compatible object store, as a local directory.
#
# Two builds are produced from the same checkout:
#   /src        g++, -g -O1 -fno-omit-frame-pointer, OpenSSL crypto backend.  The
#               reference build, and the one the CI's Linux jobs use; /src/src/s3fs is
#               the binary a user would install.
#   /src-asan   clang++ at -O0 with AddressSanitizer and UndefinedBehaviorSanitizer, as
#               in test/run_tests_using_sanitizers.sh.  Use it to confirm memory-safety
#               findings and to run the tests again under the sanitizers.
#
# A scan has no network, so everything the tests reach for is fetched here:
#   - S3Proxy, the local S3 server the integration tests run against
#   - pjdfstest, whose POSIX conformance tests the integration suite runs
#
# threat_model.md says how to run the tests and which of them need a mount.
FROM docker.io/library/ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

# These are the packages .github/workflows/linux-ci-helper.sh installs for ubuntu:24.04,
# plus clang and its sanitizer runtime for the second build and perl for the prove(1)
# that drives pjdfstest.  Of the rest: default-jre-headless runs S3Proxy, mailcap
# supplies the /etc/mime.types that s3fs reads to guess an object's Content-Type, and
# locales-all is needed by the tests that use non-ASCII file names.
RUN apt-get update && apt-get install -y --no-install-recommends \
      acl attr autoconf automake autotools-dev build-essential ca-certificates clang \
      curl default-jre-headless fuse3 g++ git libclang-rt-dev libcurl4-openssl-dev \
      libfuse3-dev libssl-dev libtool libxml2-dev locales-all mailcap openssl perl \
      pkg-config procps \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The test helpers sign raw S3 requests with curl's --aws-sigv4, and the CI installs a
# newer static curl on this distribution because the packaged 8.5 mis-signs a query
# parameter whose value contains a space.  Take the same binary from the same place, at
# the version and checksum the repository pins: without it test_rename_onto_open_file
# fails on a request whose prefix contains one.
RUN if [ "$(uname -m)" = "x86_64" ]; then \
      eval "$(grep -E '^(CURL_DIRECT_VERSION|CURL_DIRECT_URL|CURL_HASH_X86_64)=' /src/.github/workflows/linux-ci-helper.sh)" \
   && curl --fail --location --silent --output /tmp/curl "${CURL_DIRECT_URL}" \
   && echo "${CURL_HASH_X86_64}  /tmp/curl" | sha256sum --check \
   && install -m 0755 /tmp/curl /usr/local/bin/curl \
   && rm -f /tmp/curl \
   && curl --version | head -1; \
    else \
      echo "WARNING: no pinned curl for $(uname -m): keeping the distribution's"; \
    fi

# The integration suite downloads S3Proxy and pjdfstest the first time it runs, which a
# scan cannot do.  Put both where it looks for them, at the versions and checksums the
# repository itself pins, so that this file does not go stale when they are bumped.
RUN cd /src/test \
 && eval "$(grep -E '^(S3PROXY_VERSION|S3PROXY_HASH|PJDFSTEST_HASH)=' integration-test-common.sh)" \
 && curl --fail --location --silent --output "s3proxy-${S3PROXY_VERSION}" \
      "https://github.com/gaul/s3proxy/releases/download/s3proxy-${S3PROXY_VERSION}/s3proxy" \
 && echo "${S3PROXY_HASH}  s3proxy-${S3PROXY_VERSION}" | sha256sum --check \
 && chmod +x "s3proxy-${S3PROXY_VERSION}" \
 && curl --fail --location --silent --output /tmp/pjdfstest.tar.gz \
      "https://api.github.com/repos/pjd/pjdfstest/tarball/${PJDFSTEST_HASH}" \
 && tar zxf /tmp/pjdfstest.tar.gz \
 && rm -f /tmp/pjdfstest.tar.gz \
 && ln -s "pjd-pjdfstest-$(printf '%.7s' "${PJDFSTEST_HASH}")" pjdfstest \
 && (cd pjdfstest && autoreconf -ifs && ./configure && make)

# 1) Reference build: the OpenSSL backend the Linux CI jobs use, built with debug info
#    and frame pointers in place of the plain -O of those jobs.
RUN ./autogen.sh \
 && ./configure --with-openssl CXXFLAGS="-g -O1 -fno-omit-frame-pointer" \
 && make --jobs="$(nproc)" \
 && ./src/s3fs --version

# 2) Sanitizer build, in a copy of the tree so that the reference build stays intact.
#    -Wno-cpp silences the _FORTIFY_SOURCE warning that -O0 provokes.  Note that the
#    project builds with -fno-exceptions, so an allocation failure aborts rather than
#    throwing.
RUN cp -a /src /src-asan \
 && cd /src-asan \
 && make clean \
 && ./configure --with-openssl CXX=clang++ \
      CXXFLAGS="-g -O0 -Wno-cpp -fsanitize=address,undefined -fsanitize-address-use-after-scope" \
 && make --jobs="$(nproc)" \
 && ./src/s3fs --version

# Defaults for anyone running the sanitized binaries in this image.
ENV ASAN_OPTIONS=detect_leaks=1:detect_stack_use_after_return=1:abort_on_error=1:symbolize=1 \
    UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1

# The unit tests need no mount, so run them in both builds: a failure here means the
# image is broken.  It is reported but does not abort the build.
RUN make --jobs="$(nproc)" check -C /src/src \
      || { cat /src/src/test-suite.log; echo "WARNING: unit tests failed in the reference build"; }
RUN make --jobs="$(nproc)" check -C /src-asan/src \
      || { cat /src-asan/src/test-suite.log; echo "WARNING: unit tests failed in the sanitizer build"; }

# The integration suite mounts s3fs over a local S3Proxy, so it needs /dev/fuse and
# CAP_SYS_ADMIN and cannot run during this build.  In a privileged container it runs
# offline, from either tree:
#   make check -C /src/test               one option set, a few minutes
#   make ALL_TESTS=1 check -C /src/test   all thirteen option sets, about an hour
