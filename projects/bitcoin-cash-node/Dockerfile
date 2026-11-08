FROM debian:bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive

# Follow doc/build-unix-deb.md and contrib/buildenv/Dockerfile, without Qt.
# Fetch Python test dependencies now: the finished environment runs offline.
RUN apt-get update && apt-get install -y --no-install-recommends \
      bash bison bsdmainutils build-essential ca-certificates cmake git \
      libboost-chrono-dev libboost-filesystem-dev libboost-system-dev \
      libboost-test-dev libboost-thread-dev libdb++-dev libdb-dev libevent-dev \
      libgmp-dev libminiupnpc-dev libnatpmp-dev libssl-dev libzmq3-dev \
      locales ninja-build pkg-config python3 python3-scipy python3-zmq zlib1g-dev \
    && echo 'de_DE.UTF-8 UTF-8' >> /etc/locale.gen \
    && locale-gen \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: preserve source, test data, build tree and unstripped binaries.
COPY . /src
WORKDIR /src

# Debug enables BCHN's debug symbols and lock-order checks. Keep normal hardening.
# Limit compiler memory/CPU demand, including on smaller local Docker machines.
RUN nice -n 19 cmake -S /src -B /src/build -G Ninja \
      -DCMAKE_BUILD_TYPE=Debug \
      -DCMAKE_C_FLAGS="-fno-omit-frame-pointer" \
      -DCMAKE_CXX_FLAGS="-fno-omit-frame-pointer" \
      -DBUILD_BITCOIN_DAEMON=ON \
      -DBUILD_BITCOIN_CLI=ON \
      -DBUILD_BITCOIN_TX=ON \
      -DBUILD_BITCOIN_WALLET=ON \
      -DBUILD_BITCOIN_QT=OFF \
      -DENABLE_TEST=ON \
      -DENABLE_MAN=OFF \
    && nice -n 19 cmake --build /src/build --parallel 2

# Boost unit tests are EXCLUDE_FROM_ALL in cmake/modules/TestSuite.cmake.
RUN nice -n 19 cmake --build /src/build --target test_bitcoin --parallel 2

# Tests are run explicitly after the scanner's final layer is added; see threat_model.md.
CMD ["bash"]
