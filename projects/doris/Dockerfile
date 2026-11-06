# A current userspace for the scanner's tools, with Node for the FE UI.
FROM node:22-bookworm-slim

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        autoconf automake bash binutils-dev bison byacc bzip2 ca-certificates \
        curl file flex g++ gettext git gperf help2man krb5-user libaio1 \
        libcurl4-openssl-dev libffi-dev libiberty-dev libkrb5-dev libncurses5 \
        libncurses-dev libssl-dev libtool libtool-bin libxml2-dev make \
        mariadb-client nasm openjdk-17-jdk-headless patch pkg-config procps \
        python-is-python3 python3 python3-pip \
        python3-venv texinfo unzip util-linux wget xz-utils zip zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# branch-4.2's docker/compilation/Dockerfile selects LDB 0.25. Install the
# compiler directly instead of pulling a 2 GB image of master dependencies.
RUN curl -fL --retry 3 https://github.com/amosbird/ldb_toolchain_gen/releases/download/v0.25/ldb_toolchain_gen.sh \
        -o /tmp/ldb_toolchain_gen.sh \
    && echo '09d4a300a5d55302582f8291a7309474627ecdec3648ee9f9c912244b2d4472e  /tmp/ldb_toolchain_gen.sh' | sha256sum -c -
RUN bash /tmp/ldb_toolchain_gen.sh /var/local/ldb-toolchain \
    && rm /tmp/ldb_toolchain_gen.sh

RUN curl -fL --retry 3 https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.9/apache-maven-3.9.9-bin.tar.gz \
        -o /tmp/maven.tar.gz \
    && mkdir -p /opt/maven \
    && tar -xzf /tmp/maven.tar.gz -C /opt/maven --strip-components=1 \
    && rm /tmp/maven.tar.gz

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    MAVEN_HOME=/opt/maven \
    DORIS_THIRDPARTY=/src/thirdparty \
    DORIS_HOME=/src \
    CARGO_HOME=/opt/cargo \
    RUSTUP_HOME=/opt/rustup \
    REPOSITORY_URL=https://doris-thirdparty-repo.bj.bcebos.com/thirdparty \
    BUILD_TYPE=ASAN \
    USE_AVX2=0 \
    STRIP_DEBUG_INFO=OFF \
    CCACHE_DISABLE=1 \
    FE_MAVEN_THREADS=4 \
    FE_UT_PARALLEL=1 \
    MAVEN_OPTS="-Xmx4g"
ENV PATH="/opt/cargo/bin:/opt/maven/bin:/usr/lib/jvm/java-17-openjdk-amd64/bin:/var/local/ldb-toolchain/bin:/src/thirdparty/installed/bin:${PATH}"

# The enrolled branch requires the same Rust compiler for Lance and Paimon.
RUN curl -fsSL --retry 3 https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && sh /tmp/rustup-init.sh -y --no-modify-path --profile minimal --default-toolchain 1.94.0 \
    && rm /tmp/rustup-init.sh

# XZ's autogen.sh requires Debian's separate autopoint package. Keep this
# addition after the toolchain setup so existing compiler layers remain reusable.
RUN apt-get update \
    && apt-get install -y --no-install-recommends autopoint \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Cache dependencies separately from the application sources. Use Doris' own
# archive mirror, with upstream URL fallbacks and the branch's checksum checks;
# this also avoids the unreliable Apache archive download seen for ORC 1.9.0.
COPY env.sh /src/env.sh
COPY thirdparty /src/thirdparty
ARG BUILD_JOBS
# Preserve downloads across retries. When the dependency definitions change,
# unpack and patch fresh sources instead of reusing a previous patched tree.
# Try TimSort's raw URL first; unauthenticated API requests can be rate limited
# on shared runners. Keep the contents API as a fallback for the raw host.
# download-thirdparty.sh verifies the enrolled branch's checksum either way.
RUN --mount=type=cache,id=oss-scanner-doris-4.2-src,target=/src/thirdparty/src,sharing=locked \
    find /src/thirdparty/src -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} + \
    && (curl -fL --retry 3 --connect-timeout 15 --max-time 60 \
        'https://raw.githubusercontent.com/timsort/cpp-TimSort/3.x.y/include/gfx/timsort.hpp' \
        -o /src/thirdparty/src/timsort.hpp \
    || curl -fL --retry 3 --connect-timeout 15 --max-time 60 -H 'Accept: application/vnd.github.raw+json' \
        'https://api.github.com/repos/timsort/cpp-TimSort/contents/include/gfx/timsort.hpp?ref=3.x.y' \
        -o /src/thirdparty/src/timsort.hpp) \
    && bash ./thirdparty/download-thirdparty.sh

# Checkpoint the dependency batches so a later failure does not discard every
# compiled library. Follow the branch's upstream order; the last call builds
# the remainder of its default package list, starting at gRPC.
RUN --mount=type=cache,id=oss-scanner-doris-4.2-src,target=/src/thirdparty/src,sharing=locked \
    build_jobs="${BUILD_JOBS:-$(nproc)}" \
    && CARGO_BUILD_JOBS="${build_jobs}" bash ./thirdparty/build-thirdparty.sh -j "${build_jobs}" \
        jindofs juicefs odbc openssl libevent zlib crc32c lz4 bzip lzo2 zstd \
        boost abseil gflags gtest glog protobuf rapidjson
RUN --mount=type=cache,id=oss-scanner-doris-4.2-src,target=/src/thirdparty/src,sharing=locked \
    build_jobs="${BUILD_JOBS:-$(nproc)}" \
    && CARGO_BUILD_JOBS="${build_jobs}" bash ./thirdparty/build-thirdparty.sh -j "${build_jobs}" \
        snappy gperftools curl re2 hyperscan thrift leveldb brpc lzma libunwind \
        jemalloc_doris rocksdb krb5 cyrus_sasl librdkafka flatbuffers orc cares
RUN --mount=type=cache,id=oss-scanner-doris-4.2-src,target=/src/thirdparty/src,sharing=locked \
    build_jobs="${BUILD_JOBS:-$(nproc)}" \
    && CARGO_BUILD_JOBS="${build_jobs}" bash ./thirdparty/build-thirdparty.sh -j "${build_jobs}" --continue grpc

# Scanner contract: retain the full checkout, generated bindings, UI dependencies
# and ASan build trees at /src for offline analysis and incremental reproducers.
COPY . /src
ARG DORIS_BUILD_JOBS=8
# The 4.2 UI uses webpack 4, which needs its legacy hashes on Node's OpenSSL 3.
RUN core_jobs="$(nproc)" \
    && if (( core_jobs > DORIS_BUILD_JOBS )); then core_jobs="${DORIS_BUILD_JOBS}"; fi \
    && NODE_OPTIONS=--openssl-legacy-provider bash ./build.sh --fe --be --cloud -j "${core_jobs}"

# branch-4.2 defaults this flag to false. Use the authenticated FE HTTP posture
# required by the supplied threat model, without changing the source default.
RUN printf '\n%s\n' 'enable_all_http_auth = true' >> output/fe/conf/fe.conf

# Exercise the upstream FE unit-test driver online to populate Surefire and its
# test dependencies as well as the runtime dependencies fetched by build.sh.
RUN bash ./run-fe-ut.sh --run org.apache.doris.mysql.MysqlPasswordTest

# Auditing runs offline. Make the normal Maven commands and run-fe-ut.sh use
# only the local repository, then check that the same small test works offline.
RUN mkdir -p /root/.m2 \
    && printf '%s\n' '<settings><offline>true</offline></settings>' > /root/.m2/settings.xml \
    && bash ./run-fe-ut.sh --run org.apache.doris.mysql.MysqlPasswordTest

# FE/BE packages: /src/output/. Cloud package: /src/cloud/output/.
# FE tests: bash ./run-fe-ut.sh --run <class>.
# Native builds: BUILD_TYPE=ASAN bash ./build.sh --be --cloud -j 1.
# Read the enrollment's threat_model.md before exercising services. Keep FE
# enable_all_http_auth=true; check its effective value, including fe_custom.conf,
# and preserve the model's client/internal boundaries.
CMD ["/bin/bash"]
