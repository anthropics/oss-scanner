# ecCodes: ECMWF's decoder/encoder for the WMO formats GRIB (editions 1 and 2) and BUFR (editions 3 and 4).
# Everything the audit needs (ecbuild, libaec, the test data) is fetched here, before the network is removed.

FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang libclang-rt-18-dev gdb cmake ninja-build git curl python3 perl \
      libnetcdf-dev libopenjp2-7-dev libpng-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# ecCodes needs libaec >= 1.1.4 for CCSDS; Ubuntu 24.04 ships 1.1.2. libaec is a dependency, out of scope.
RUN git clone --depth 1 --branch v1.1.4 https://github.com/MathisRosenhauer/libaec.git /deps/libaec \
    && cmake -S /deps/libaec -B /deps/libaec/build -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo \
    && cmake --build /deps/libaec/build && cmake --install /deps/libaec/build && ldconfig

# ecbuild: CMakeLists.txt finds it at ../ecbuild, so a re-configure also works offline.
RUN git clone --depth 1 --branch 3.16.0 https://github.com/ecmwf/ecbuild.git /ecbuild

# scanner contract: the checkout lives inside the image, at /src
# RUN git clone --branch develop https://github.com/ecmwf/eccodes.git /src
COPY . /src
WORKDIR /src

ENV ECCODES_CMAKE_OPTS="-G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DENABLE_EXTRA_TESTS=ON \
      -DENABLE_ECCODES_THREADS=ON -DENABLE_PNG=ON -DENABLE_JPG_LIBJASPER=OFF -DENABLE_FORTRAN=OFF"

# Normal build with debug info (CMakePresets.json "ci").
RUN cmake -S /src -B /src/build ${ECCODES_CMAKE_OPTS} \
      -DCMAKE_C_FLAGS="-g -fno-omit-frame-pointer" -DCMAKE_CXX_FLAGS="-g -fno-omit-frame-pointer" \
    && cmake --build /src/build

# ASan+UBSan build of the library, tools and tests (CMakePresets.json "asan-ubsan").
RUN cmake -S /src -B /src/build-asan ${ECCODES_CMAKE_OPTS} \
      -DCMAKE_C_FLAGS="-g -fsanitize=address,undefined -fno-sanitize=vptr -fno-omit-frame-pointer" \
      -DCMAKE_CXX_FLAGS="-g -fsanitize=address,undefined -fno-sanitize=vptr -fno-omit-frame-pointer" \
      -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address,undefined" \
      -DCMAKE_SHARED_LINKER_FLAGS="-fsanitize=address,undefined" \
    && cmake --build /src/build-asan
ENV ASAN_OPTIONS=detect_leaks=0

# Test data (real GRIB/BUFR/GTS/METAR files, ~260 MB) while the network is up, then the regression tests.
# A failing test does not fail the image.
RUN cd /src/build \
    && ctest -L download_data -j 16 --repeat until-pass:5 \
    && cp -R /src/build/data/. /src/build-asan/data/ \
    && (ctest -LE download_data -j"$(nproc)" --timeout 600 > ctest.log 2>&1 \
        || echo "WARNING: ecCodes tests reported failures; see /src/build/ctest.log")
