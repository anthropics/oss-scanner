FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUTF8=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates cmake curl gdb git pkg-config python3 python3-venv \
      libssl-dev libzmq3-dev libunbound-dev libsodium-dev libunwind-dev libreadline-dev \
      libhidapi-dev libusb-1.0-0-dev libprotobuf-dev protobuf-compiler \
      libboost-chrono-dev libboost-date-time-dev libboost-filesystem-dev libboost-locale-dev \
      libboost-program-options-dev libboost-regex-dev libboost-serialization-dev libboost-system-dev \
      libboost-thread-dev \
    && rm -rf /var/lib/apt/lists/*

# The FCMP++ code needs Rust 1.85 or newer, and Ubuntu 24.04's rustc is older.
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH="/usr/local/cargo/bin:${PATH}"
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path --profile minimal \
    && rustc --version

# Python packages for tests/functional_tests.
RUN python3 -m venv /opt/monero-test-env \
    && /opt/monero-test-env/bin/pip install --no-cache-dir requests psutil monotonic zmq deepdiff
ENV PATH="/opt/monero-test-env/bin:${PATH}"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The scanner's clone is not recursive.
RUN git submodule update --init --recursive --depth=1

RUN cmake -S /src -B /src/build \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DCMAKE_C_FLAGS="-fno-omit-frame-pointer" \
      -DCMAKE_CXX_FLAGS="-fno-omit-frame-pointer" \
      -DBUILD_TESTS=ON \
    && cmake --build /src/build -j"$(nproc)"

# The build downloaded every crate already. Keep cargo off the network from here on.
ENV CARGO_NET_OFFLINE=true

# Run the unit tests once, with the filter from Monero's CI (the DNSResolver and AddressFromURL tests need
# the network). A failure or timeout prints a warning and doesn't fail the build.
RUN cd /src/build/tests/unit_tests \
    && (timeout --kill-after=5 600 ./unit_tests --data-dir=/src/tests/data \
        --gtest_filter='-DNSResolver.*:AddressFromURL.*:select_outputs.*' \
        || echo "WARNING: unit_tests reported failures (or timed out)")
