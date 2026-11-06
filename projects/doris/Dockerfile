# Reuse Doris' official compiler, JDK, Maven and Rust installations. Do not reuse
# its master-branch native libraries for a branch-4.2 scan.
FROM apache/doris:build-env-ldb-toolchain-no-avx2-latest AS build_dependencies

# Keep a current userspace for the scanner's additional tools.
FROM node:22-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        autoconf automake bash binutils-dev bison byacc bzip2 ca-certificates \
        curl file flex g++ gettext git gperf help2man krb5-user libaio1 \
        libcurl4-openssl-dev libffi-dev libiberty-dev libkrb5-dev libncurses5 \
        libncurses-dev libssl-dev libtool libtool-bin libxml2-dev make \
        mariadb-client nasm patch pkg-config procps python3 python3-pip \
        python3-venv texinfo unzip util-linux wget xz-utils zip zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build_dependencies /var/local/ldb-toolchain /var/local/ldb-toolchain
COPY --from=build_dependencies /usr/lib/jvm/jdk-17.0.2 /usr/lib/jvm/jdk-17.0.2
COPY --from=build_dependencies /usr/share/maven /usr/share/maven
COPY --from=build_dependencies /opt/cargo /opt/cargo
COPY --from=build_dependencies /opt/rustup /opt/rustup

ENV JAVA_HOME=/usr/lib/jvm/jdk-17.0.2 \
    MAVEN_HOME=/usr/share/maven \
    DORIS_THIRDPARTY=/src/thirdparty \
    DORIS_HOME=/src \
    CARGO_HOME=/opt/cargo \
    RUSTUP_HOME=/opt/rustup \
    BUILD_TYPE=ASAN \
    USE_AVX2=0 \
    STRIP_DEBUG_INFO=OFF \
    CCACHE_DISABLE=1 \
    FE_MAVEN_THREADS=4 \
    FE_UT_PARALLEL=1 \
    MAVEN_OPTS="-Xmx4g" \
    DEBIAN_FRONTEND=noninteractive
ENV PATH="/opt/cargo/bin:/usr/share/maven/bin:/usr/lib/jvm/jdk-17.0.2/bin:/var/local/ldb-toolchain/bin:/src/thirdparty/installed/bin:${PATH}"

# Scanner contract: the checkout and all build outputs are retained at /src.
COPY . /src
WORKDIR /src

# Build the native dependencies from the enrolled branch's pinned definitions,
# including its own Hadoop, Paimon and Lance versions. This is intentionally a
# source bootstrap: a master prebuilt can have incompatible headers/libraries.
# Fetch native submodules, generate protocol bindings, build the UI, FE, BE and
# Cloud Meta Service, and resolve Maven/npm dependencies while networking works.
# Retain the ASan build trees for incremental native reproducers and debugging.
ARG BUILD_JOBS=8
RUN bash ./thirdparty/build-thirdparty.sh -j "${BUILD_JOBS}" \
    && bash ./build.sh --fe --be --cloud -j "${BUILD_JOBS}" \
    && rm -rf /src/thirdparty/src

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
