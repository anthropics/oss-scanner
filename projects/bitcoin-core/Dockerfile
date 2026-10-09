FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang-18 \
    CXX=clang++-18 \
    PYTHONUTF8=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang-18 cmake git libboost-dev \
      libcapnp-dev capnproto libclang-rt-18-dev libsqlite3-dev libzmq3-dev \
      llvm-18 ninja-build pkg-config python3 python3-pip python3-venv python3-zmq \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv --system-site-packages /opt/bitcoin-test-env \
    && /opt/bitcoin-test-env/bin/pip install --no-cache-dir pycapnp==2.2.1
ENV PATH="/opt/bitcoin-test-env/bin:${PATH}"

COPY . /src
WORKDIR /src

RUN git clone --depth=1 https://github.com/bitcoin-core/qa-assets /qa-assets
ENV DIR_UNIT_TEST_DATA=/qa-assets/unit_test_data \
    LLVM_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18 \
    ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18 \
    UBSAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18

RUN cmake -S /src -B /src/build -G Ninja \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DCMAKE_C_FLAGS="-fno-omit-frame-pointer" \
      -DCMAKE_CXX_FLAGS="-fno-omit-frame-pointer" \
      -DBUILD_TESTS=ON -DBUILD_BENCH=ON -DBUILD_GUI=OFF \
      -DENABLE_WALLET=ON -DENABLE_IPC=ON -DWITH_ZMQ=ON \
      -DWITH_CCACHE=OFF \
    && cmake --build /src/build -j10

RUN cmake --preset=libfuzzer \
      -DCMAKE_C_COMPILER=clang-18 -DCMAKE_CXX_COMPILER=clang++-18 \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DWITH_CCACHE=OFF \
    && cmake --build /src/build_fuzz -j10

RUN ctest --test-dir /src/build --output-on-failure -j2 --timeout 300 \
    && python3 /src/build/test/functional/test_runner.py -j2 \
      interface_ipc.py interface_zmq.py p2p_invalid_messages.py wallet_basic.py
