# Elements (elements-23.3.x line), autotools build: the daemon, the CLI, the wallet and the
# Qt GUI, plus a clang sanitizer tree to reproduce findings against.
#
# This branch predates the CMake migration, so the build is ./autogen.sh && ./configure && make.
# Dependencies come from apt rather than the repository's depends/ tree: depends/ builds Qt and
# Berkeley DB from source, which takes far longer than the build budget allows. Ubuntu's Qt5 and
# Berkeley DB work; BDB 5.3 is not the 4.8 the release builds use, so we pass
# --with-incompatible-bdb (below) and accept BDB 5.3-format legacy wallets, which is fine for
# auditing. The GUI is built because it is in scope.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUTF8=1 \
    CCACHE_DIR=/ccache \
    CCACHE_MAXSIZE=10G

# Toolchain and every library the daemon, wallet and GUI need, from apt.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates ccache pkg-config git bison \
      autoconf automake libtool m4 \
      g++-14 clang-20 llvm-20 libclang-rt-20-dev \
      libboost-dev libevent-dev libsqlite3-dev libdb++-dev \
      libzmq3-dev libgmp-dev \
      qtbase5-dev qttools5-dev-tools libqrencode-dev \
      python3 python3-venv python3-dev python3-zmq \
      bsdmainutils e2fsprogs procps \
    && rm -rf /var/lib/apt/lists/*

# clang-20 as the unversioned clang that the sanitizer tree uses.
RUN update-alternatives --install /usr/bin/clang clang /usr/bin/clang-20 100 \
    && update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-20 100 \
    && update-alternatives --install /usr/bin/llvm-symbolizer llvm-symbolizer /usr/bin/llvm-symbolizer-20 100

# Functional-test framework, in a venv so PATH picks it up the way the tests expect.
RUN python3 -m venv --system-site-packages /opt/elements-test-env \
    && /opt/elements-test-env/bin/pip install --no-cache-dir pyyaml
ENV PATH="/opt/elements-test-env/bin:${PATH}" \
    LLVM_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-20 \
    ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-20 \
    UBSAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-20

# Script assets for the unit tests. CI downloads this per run; an audit has no network, so it is here.
RUN git clone --depth=1 --filter=blob:none --sparse \
      https://github.com/ElementsProject/qa-assets /qa-assets \
    && git -C /qa-assets sparse-checkout set unit_test_data
ENV DIR_QA_ASSETS=/qa-assets \
    DIR_UNIT_TEST_DATA=/qa-assets/unit_test_data

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Generate configure from configure.ac. The checkout may carry generated build artefacts from a
# developer's earlier in-tree build; the out-of-tree configure below aborts with "source directory
# already configured" if the vendored subprojects still have one, so clear them.
RUN ./autogen.sh \
    && for d in /src/src/secp256k1 /src/src/minisketch /src/src/univalue /src/src/leveldb; do \
         if [ -d "$d" ]; then \
           find "$d" \( -name 'config.status' -o -name 'config.log' -o -name 'Makefile' -o -name 'libtool' \) -delete; \
           find "$d" \( -name '*.o' -o -name '*.lo' -o -name '*.la' -o -name '.deps' -o -name '.libs' -o -name 'autom4te.cache' \) -exec rm -rf {} + ; \
         fi; \
       done

# Build 1: the daemon, the wallet (descriptor + legacy) and the Qt GUI, -O2 -g, as a release is built.
# --with-incompatible-bdb accepts Ubuntu's Berkeley DB 5.3 for the legacy wallet.
RUN mkdir -p /src/build && cd /src/build \
    && /src/configure \
         --enable-wallet \
         --with-incompatible-bdb \
         --with-gui=qt5 \
         --with-utils \
         --with-daemon \
         --with-libs \
         --enable-zmq \
         --enable-tests \
         --enable-bench \
         --disable-fuzz-binary \
         --disable-maintainer-mode \
         CC=gcc-14 CXX=g++-14 \
         CFLAGS="-O2 -g -fno-omit-frame-pointer" \
         CXXFLAGS="-O2 -g -fno-omit-frame-pointer" \
    && make -j"$(nproc)" \
    && ccache --show-stats

# Build 2: the same sources with clang and the sanitizers of Elements' ASan CI job, so a reproducer
# can run against an instrumented node. Wallet and GUI stay on. --with-sanitizers disables seccomp.
RUN mkdir -p /src/build_asan && cd /src/build_asan \
    && /src/configure \
         --enable-wallet \
         --with-incompatible-bdb \
         --with-gui=qt5 \
         --with-utils \
         --with-daemon \
         --enable-zmq \
         --enable-tests \
         --disable-bench \
         --disable-fuzz-binary \
         --disable-maintainer-mode \
         --with-sanitizers=address,float-divide-by-zero,integer,undefined \
         CC=clang CXX=clang++ \
         CFLAGS="-g -fno-omit-frame-pointer -ftrivial-auto-var-init=pattern" \
         CXXFLAGS="-g -fno-omit-frame-pointer -ftrivial-auto-var-init=pattern" \
    && make -j"$(nproc)" \
    && ccache --show-stats

# Fail the build only on what cannot flake: the binaries exist and start.
# The unit-test binary on this branch is test_bitcoin; the GUI is src/qt/elements-qt.
# elements-wallet -version prints its version but exits non-zero, hence the pipe. The GUI cannot be
# launched here (no display, no offscreen Qt plugin), so it is checked by its embedded Qt version.
RUN test -x /src/build/src/elementsd \
    && test -x /src/build/src/elements-cli \
    && test -x /src/build/src/elements-wallet \
    && test -x /src/build/src/elements-tx \
    && test -x /src/build/src/qt/elements-qt \
    && test -x /src/build/src/test/test_bitcoin \
    && /src/build/src/elementsd -version \
    && /src/build/src/elementsd -help 2>&1 | grep -q -- '-disablewallet' \
    && /src/build/src/elements-wallet -version 2>&1 | grep -q 'elements-wallet version' \
    && strings /src/build/src/qt/elements-qt | grep -q 'libQt5' \
    && test -f "$DIR_UNIT_TEST_DATA/script_assets_test.json" \
    && ASAN_OPTIONS=detect_leaks=0 /src/build_asan/src/elementsd -version > /dev/null

# Show in the build log that the tests run offline, without failing the build on a broken or flaky test.
RUN (timeout --kill-after=5 1200 /src/build/src/test/test_bitcoin \
      || echo "WARNING: unit tests reported failures") \
    && (timeout --kill-after=5 300 python3 /src/build/test/functional/test_runner.py -j"$(nproc)" \
      feature_confidential_transactions.py feature_issuance.py feature_sighash_rangeproof.py \
      || echo "WARNING: functional tests reported failures")

# Leave the agent where the artefacts are.
WORKDIR /src
