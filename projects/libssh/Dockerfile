FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        cmake \
        clang \
        clang-tools \
        doxygen \
        git \
        llvm \
        libcmocka-dev \
        libfido2-dev \
        libp11-dev \
        libssl-dev \
        libz-dev \
        libkrb5-dev \
        ninja-build \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN cmake -S /src -B /src/build -G Ninja \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_C_FLAGS="-g -fno-omit-frame-pointer" \
      -DWITH_BLOWFISH_CIPHER=ON -DWITH_SFTP=ON -DWITH_SERVER=ON -DWITH_ZLIB=ON -DWITH_PCAP=ON -DWITH_DEBUG_CRYPTO=ON -DWITH_DEBUG_PACKET=ON -DWITH_DEBUG_CALLTRACE=ON \
      -DWITH_EXAMPLES=ON \
      -DUNIT_TESTING=ON \
    && cmake --build /src/build -j"$(nproc)"

RUN cd /src/build && (ctest --output-on-failure -j"$(nproc)" --timeout 300 || echo "WARNING: ctest reported failures")
