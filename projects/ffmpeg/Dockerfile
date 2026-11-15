# FFmpeg under clang's AddressSanitizer and UndefinedBehaviorSanitizer with debug info
# and extra assertions. The main build leaves out the hand written assembly so that
# every C code path is the one that runs; a second build keeps it. The FATE sample
# suite is fetched to /src/fate-suite so that the regression tests work without a
# network.
FROM docker.io/library/debian:trixie

ENV DEBIAN_FRONTEND=noninteractive \
    ASAN_SYMBOLIZER_PATH=/usr/lib/llvm-19/bin/llvm-symbolizer \
    UBSAN_OPTIONS=print_stacktrace=1 \
    CONFIGURE_FLAGS="--cc=clang-19 --cxx=clang++-19 --optflags=-O1 --enable-debug=3 \
      --assert_level=2 --disable-stripping --enable-gpl --samples=/src/fate-suite \
      --extra-cflags=-fno-sanitize-recover=undefined \
      --extra-cflags=-fsanitize-recover=pointer-overflow" \
    LIBRARY_FLAGS="--enable-gnutls --enable-libxml2 --enable-libx264 --enable-libvpx \
      --enable-libtheora --enable-libvorbis --enable-libopus --enable-libmp3lame \
      --enable-libass --enable-libfreetype --enable-libharfbuzz --enable-libfontconfig \
      --enable-libfribidi"

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang-19 llvm-19 libclang-rt-19-dev \
      nasm pkg-config git rsync \
      zlib1g-dev libbz2-dev liblzma-dev libgnutls28-dev libxml2-dev \
      libx264-dev libvpx-dev libtheora-dev libvorbis-dev libopus-dev libmp3lame-dev \
      libass-dev libfreetype-dev libharfbuzz-dev libfontconfig-dev libfribidi-dev \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the repository is the build context and lives at /src.
COPY . /src
WORKDIR /src
RUN printf 'build-asm/\nbuild-fuzz/\nfate-suite/\n' >> .git/info/exclude

# The head of every pull request, open and closed, to check that a finding is not already fixed.
RUN git fetch --quiet https://code.ffmpeg.org/FFmpeg/FFmpeg.git '+refs/pull/*/head:refs/pull/*/head' \
    || echo "WARNING: pull request fetch failed, duplicates cannot be checked"

# The out of tree builds have to be configured before the in tree build creates
# config.h. The libFuzzer targets need --enable-ossfuzz, which leaves the tools
# without a codec list, so they get a build of their own.
RUN mkdir -p build-fuzz/tools && cd build-fuzz \
    && ../configure $CONFIGURE_FLAGS --toolchain=clang-asan-ubsan-fuzz --disable-asm \
      --enable-ossfuzz --disable-programs --disable-doc --disable-devices \
    && make -j"$(nproc)" tools/target_dem_fuzzer tools/target_io_dem_fuzzer \
                         tools/target_sws_fuzzer tools/target_swr_fuzzer

RUN mkdir -p build-asm && cd build-asm \
    && ../configure $CONFIGURE_FLAGS --toolchain=clang-asan-ubsan $LIBRARY_FLAGS \
    && make -j"$(nproc)"

RUN ./configure $CONFIGURE_FLAGS --toolchain=clang-asan-ubsan --disable-asm $LIBRARY_FLAGS \
    && make -j"$(nproc)"

# The samples make the full regression suite available; a failing test must not fail the build.
RUN make fate-rsync || echo "WARNING: fate-suite download failed, only sample-free tests will run"
RUN make -j"$(nproc)" -k fate || echo "WARNING: fate reported failures"
RUN make -C build-asm -j"$(nproc)" -k fate-checkasm || echo "WARNING: checkasm reported failures"
