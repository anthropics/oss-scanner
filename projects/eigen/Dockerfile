# OSS Scanner build for Eigen (https://gitlab.com/libeigen/eigen).
#
# Eigen is header-only, so what can be scanned is template code instantiated by a driver: a test, or a program
# written against the public headers. This image configures one CMake tree, /src/build, with the sanitizer flags of
# Eigen's CI job build:linux:cross:x86-64:clang-19:default:asan-ubsan (clang-19, ASan + UBSan, no UB recovery). Here the
# flags apply to every target, not only to the tests, so the C-ABI BLAS and LAPACK libraries are instrumented too.
#
# The image prebuilds those libraries and the tests that cover the entry points threat_model.md lists. Any other test
# builds offline in the same tree:
#
#   cmake --build /src/build --target <test>             # e.g. ref, product_threaded, tensor_thread_pool
#   ctest --test-dir /src/build -R '^<test>(_[0-9]+)?$' --output-on-failure
FROM ubuntu:24.04
# The optional packages enable the tests of Eigen's sparse-solver backends (CHOLMOD, UMFPACK, KLU, SPQR, SuperLU), its
# FFTW and MPFR wrappers, and the Boost.Multiprecision scalar test.
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang-19 \
    CXX=clang++-19 \
    ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-19 \
    UBSAN_OPTIONS=print_stacktrace=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang-19 libclang-rt-19-dev llvm-19 cmake ninja-build pkg-config git python3 \
      libsuitesparse-dev libsuperlu-dev libfftw3-dev libmpfrc++-dev libmpfr-dev libgmp-dev libboost-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN san="-fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer" \
    && cmake -S /src -B /src/build -G Ninja \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_C_FLAGS="$san" \
      -DCMAKE_CXX_FLAGS="$san" \
      -DCMAKE_EXE_LINKER_FLAGS="-fsanitize=address,undefined" \
      -DCMAKE_SHARED_LINKER_FLAGS="-fsanitize=address,undefined" \
      -DEIGEN_BUILD_DOC=OFF \
      -DEIGEN_BUILD_DEMOS=OFF

# Split tests build every part through the base name (sparse_basic builds sparse_basic_1 ... sparse_basic_5).
ARG PREBUILT_TESTS="serializer sizeoverflow dynalloc io zerosized indexed_view stl_iterators sparse_basic \
sparse_extra tensor_io threads_non_blocking_thread_pool threads_eventcount threads_runqueue threads_fork_join"

# An instrumented Eigen test compile peaks at a few GiB, so -j is capped at one job per 4 GiB of free memory.
RUN jobs=$(nproc); mem=$(awk '/^MemAvailable:/ { print int($2 / 4194304) }' /proc/meminfo); \
    if [ "$mem" -lt "$jobs" ]; then jobs=$mem; fi; if [ "$jobs" -lt 1 ]; then jobs=1; fi; \
    cmake --build /src/build -j"$jobs" --target blas lapack $PREBUILT_TESTS

# Run the prebuilt tests so the log shows the image works, without letting a failure abort the build.
RUN cd /src/build \
    && (ctest -R "^($(echo $PREBUILT_TESTS | tr ' ' '|'))(_[0-9]+)?\$" -j"$(nproc)" --timeout 600 \
          --output-on-failure --no-tests=error \
        || echo "WARNING: ctest reported failures")
