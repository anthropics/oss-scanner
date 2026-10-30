# Bitcoin Core, built two ways, both with the dev-mode preset minus the GUI and the fuzz binary:
#   /src/build       like a release: GCC 14 (the release compiler), -O2 -g
#   /src/build_asan  the same sources with clang and the sanitizers of Bitcoin Core's ASan CI job, to run a reproducer
#                    against an instrumented node
# ccache keeps the objects of both builds, so returning to the scanned revision after a checkout or patch is quick.
FROM ubuntu:26.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUTF8=1 \
    CCACHE_DIR=/ccache \
    CCACHE_MAXSIZE=10G

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates ccache cmake git ninja-build pkg-config \
      g++-14 clang-22 libclang-rt-22-dev llvm-22 \
      libboost-dev libsqlite3-dev libzmq3-dev libcapnp-dev capnproto \
      python3 python3-venv python3-zmq systemtap-sdt-dev \
    && rm -rf /var/lib/apt/lists/*

# pycapnp for the IPC functional tests, pinned so that the image does not change under us.
RUN python3 -m venv --system-site-packages /opt/bitcoin-test-env \
    && /opt/bitcoin-test-env/bin/pip install --no-cache-dir pycapnp==2.2.4
ENV PATH="/opt/bitcoin-test-env/bin:${PATH}"

# Script test data for the unit tests; the rest of qa-assets is not needed here.
RUN git clone --depth=1 --filter=blob:none --sparse https://github.com/bitcoin-core/qa-assets /qa-assets \
    && git -C /qa-assets sparse-checkout set unit_test_data
ENV DIR_UNIT_TEST_DATA=/qa-assets/unit_test_data \
    LLVM_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-22 \
    ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-22 \
    UBSAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-22

COPY . /src
WORKDIR /src

RUN cmake -S /src -B /src/build -G Ninja --preset dev-mode -DBUILD_GUI=OFF -DBUILD_FUZZ_BINARY=OFF \
      -DCMAKE_C_COMPILER=gcc-14 -DCMAKE_CXX_COMPILER=g++-14 \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    && cmake --build /src/build -j"$(nproc)"

RUN cmake -S /src -B /src/build_asan -G Ninja --preset dev-mode -DBUILD_GUI=OFF -DBUILD_FUZZ_BINARY=OFF \
      -DCMAKE_C_COMPILER=clang-22 -DCMAKE_CXX_COMPILER=clang++-22 \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_C_FLAGS="-fno-omit-frame-pointer -ftrivial-auto-var-init=pattern" \
      -DCMAKE_CXX_FLAGS="-fno-omit-frame-pointer -ftrivial-auto-var-init=pattern" \
      -DSANITIZERS=address,float-divide-by-zero,integer,undefined \
    && cmake --build /src/build_asan -j"$(nproc)" \
    && ccache --show-stats

# Fail the build only on what cannot flake: the bindings and data the tests need, and binaries that start.
# LeakSanitizer needs ptrace, which docker build does not allow (the scanner's container does), so it is off here.
RUN python3 -c "import capnp, zmq" \
    && test -f "$DIR_UNIT_TEST_DATA/script_assets_test.json" \
    && /src/build/bin/bitcoind -version > /dev/null \
    && ASAN_OPTIONS=detect_leaks=0 python3 /src/build_asan/test/with_sanitizer_env.py \
      /src/build_asan/bin/bitcoind -version > /dev/null

# Show in the build log that the tests run offline, without failing the build on a broken or flaky test.
RUN (timeout --kill-after=5 600 ctest --test-dir /src/build --output-on-failure -j"$(nproc)" --timeout 300 \
      || echo "WARNING: ctest reported failures") \
    && (timeout --kill-after=5 300 python3 /src/build/test/functional/test_runner.py -j"$(nproc)" \
      interface_ipc.py interface_zmq.py p2p_invalid_messages.py wallet_basic.py \
      || echo "WARNING: functional tests reported failures")
