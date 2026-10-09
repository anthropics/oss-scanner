FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang-18 cmake git libclang-rt-18-dev \
      libc6-dbg llvm-18 ninja-build python3 valgrind \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

ENV ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18 \
    UBSAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18 \
    MSAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18 \
    ASAN_OPTIONS=strict_string_checks=1:detect_stack_use_after_return=1:detect_leaks=1 \
    LSAN_OPTIONS=use_unaligned=1 \
    UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1

RUN cmake -S /src -B /src/build -G Ninja --preset=dev-mode \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DSECP256K1_VALGRIND=ON \
      -DSECP256K1_APPEND_CFLAGS=-fno-omit-frame-pointer \
    && cmake --build /src/build -j10

RUN cmake -S /src -B /src/build-asan -G Ninja --preset=dev-mode \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DCMAKE_C_COMPILER=clang-18 \
      -DSECP256K1_VALGRIND=OFF -DSECP256K1_BUILD_CTIME_TESTS=OFF \
      -DSECP256K1_APPEND_CFLAGS="-fsanitize=address,undefined -fno-sanitize-recover=undefined -fno-omit-frame-pointer" \
      -DSECP256K1_APPEND_LDFLAGS="-fsanitize=address,undefined" \
    && cmake --build /src/build-asan -j10

RUN cmake -S /src -B /src/build-int64 -G Ninja --preset=dev-mode \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DSECP256K1_TEST_OVERRIDE_WIDE_MULTIPLY=int64 -DSECP256K1_ASM=OFF \
      -DSECP256K1_VALGRIND=OFF -DSECP256K1_BUILD_CTIME_TESTS=OFF \
      -DSECP256K1_APPEND_CFLAGS=-fno-omit-frame-pointer \
    && cmake --build /src/build-int64 -j10

RUN cmake -S /src -B /src/build-int128-struct -G Ninja --preset=dev-mode \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DSECP256K1_TEST_OVERRIDE_WIDE_MULTIPLY=int128_struct \
      -DSECP256K1_ECMULT_GEN_KB=2 -DSECP256K1_ECMULT_WINDOW_SIZE=4 \
      -DSECP256K1_VALGRIND=OFF -DSECP256K1_BUILD_CTIME_TESTS=OFF \
      -DSECP256K1_APPEND_CFLAGS=-fno-omit-frame-pointer \
    && cmake --build /src/build-int128-struct -j10

RUN cmake -S /src -B /src/build-msan -G Ninja --preset=dev-mode \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DCMAKE_C_COMPILER=clang-18 \
      -DCMAKE_C_FLAGS="-fsanitize=memory -fno-omit-frame-pointer" \
      -DSECP256K1_VALGRIND=OFF -DSECP256K1_BUILD_CTIME_TESTS=ON \
    && cmake --build /src/build-msan -j10

RUN ctest --test-dir /src/build --output-on-failure -j2 --timeout 300 \
    && ctest --test-dir /src/build-asan --output-on-failure -j2 --timeout 300 \
    && ctest --test-dir /src/build-int64 --output-on-failure -j2 --timeout 300 \
    && ctest --test-dir /src/build-int128-struct --output-on-failure -j2 --timeout 300 \
    && ctest --test-dir /src/build-msan --output-on-failure -j2 --timeout 300 \
    && timeout --kill-after=5 300 /src/build-msan/bin/ctime_tests
