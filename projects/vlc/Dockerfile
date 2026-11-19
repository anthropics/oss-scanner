# OSS Scanner build for the VLC 3.0.x maintenance branch.
#
# The image contains:
#   /src/build       release-like Clang build with debug information
#   /src/build-asan  the same broad plugin set, built with GCC, AddressSanitizer,
#                    and a low-noise UBSan subset
#   /src/build-fuzz  VLC's static demux and demux+decoder libFuzzer harnesses
#   /src/fuzz-corpus the public VideoLAN fuzz corpus, fetched while networking is available
FROM debian:trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git curl \
      build-essential clang llvm lld libclang-rt-dev \
      autoconf automake autopoint gettext libtool libtool-bin pkg-config \
      flex bison gperf nasm yasm cmake ninja-build python3 xz-utils zip \
      gdb valgrind file xxd jq xvfb xauth \
      libdbus-1-dev libsystemd-dev libidn-dev libminizip-dev zlib1g-dev \
      libarchive-dev libbluray-dev libcddb2-dev libdvbpsi-dev \
      libdvdnav-dev libdvdread-dev libnfs-dev libsmbclient-dev libsmb2-dev \
      libssh2-1-dev libupnp-dev libmicrodns-dev libvncserver-dev \
      libsrt-gnutls-dev librist-dev \
      libavcodec-dev libavformat-dev libavutil-dev libswresample-dev \
      libswscale-dev libpostproc-dev \
      libebml-dev libmatroska-dev libogg-dev \
      liba52-0.7.4-dev libaom-dev libaribb24-dev libass-dev libdav1d-dev \
      libdca-dev libfaad-dev libflac-dev libgme-dev libjpeg-dev libkate-dev \
      libmad0-dev libmodplug-dev libmpcdec-dev libmpeg2-4-dev libmpg123-dev \
      libopus-dev libpng-dev libspeex-dev libspeexdsp-dev libtheora-dev \
      libvorbis-dev libvpx-dev libzvbi-dev \
      libfontconfig1-dev libfreetype-dev libfribidi-dev libharfbuzz-dev \
      libxml2-dev libgnutls28-dev libgcrypt20-dev libtag1-dev \
      libasound2-dev libpulse-dev libsamplerate0-dev libsoxr-dev \
      libx11-dev libxext-dev libxinerama-dev libxpm-dev x11proto-dev \
      libxcb1-dev libxcb-shm0-dev libxcb-composite0-dev libxcb-xv0-dev \
      libxcb-randr0-dev libxcb-keysyms1-dev \
      qtbase5-dev qttools5-dev-tools libqt5svg5-dev libqt5x11extras5-dev \
      lua5.2 liblua5.2-dev protobuf-compiler libprotobuf-dev \
      librsvg2-dev libcaca-dev \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: the checkout is the Docker build context and remains at /src.
COPY . /src
WORKDIR /src

# The public corpus is part of VideoLAN's fuzzing infrastructure. Keep it in the
# image so mutation and replay work after the scanner removes network access.
RUN git clone --depth 1 \
      https://code.videolan.org/VideoLAN.org/vlc-fuzz-corpus.git \
      /src/fuzz-corpus

# A git checkout does not contain generated Autotools files.
RUN ./bootstrap

# Broad release-like build. The Linux image cannot model every official package,
# but it enables the important parsers, network modules, Qt, and skins2.
# RealRTSP stays disabled, matching the 3.0.x configure default. The updater
# (--enable-update-check) is Windows-only code and does not compile on Linux.
RUN set -eux; \
    mkdir /src/build; \
    cd /src/build; \
    CC=clang CXX=clang++ \
    CFLAGS="-g -O2 -fno-omit-frame-pointer" \
    CXXFLAGS="-g -O2 -fno-omit-frame-pointer" \
    ../configure \
      --disable-nls \
      --enable-run-as-root \
      --enable-smb2 \
      --enable-vnc \
      --enable-srt \
      --enable-librist \
      --enable-microdns \
      --enable-dav1d \
      --enable-aom \
      --enable-gme \
      --enable-qt \
      --enable-skins2 \
      --disable-realrtsp \
      --disable-live555 \
      --disable-wayland \
      --disable-spatialaudio \
      --disable-projectm \
      --disable-vsxu; \
    make -j"$(nproc)"; \
    make -C test -j"$(nproc)" vlc-demux-run vlc-demux-dec-run

# Broad replay build with ASan plus a low-noise UBSan subset: array bounds
# (catches overruns inside one allocation, where ASan is blind), shifts,
# integer division by zero, pointer overflow, and VLA bounds. Signed-overflow
# checking is deliberately left out: timestamp arithmetic trips it constantly
# and those are not security issues. Distro libraries are intentionally not
# instrumented; sanitizer findings rooted in them need separate attribution.
# GCC is used here on purpose: VLC links every shared object with -no-undefined,
# which GCC's shared libasan satisfies, while clang's default static ASan runtime
# leaves __asan_* symbols unresolved in libvlccore.so and the plugins. The
# explicit -lasan is needed because libtool links C++ modules with -nostdlib,
# which drops the runtime GCC would otherwise add for -fsanitize=address.
RUN set -eux; \
    mkdir /src/build-asan; \
    cd /src/build-asan; \
    CC=gcc CXX=g++ \
    CFLAGS="-g -O1 -fno-omit-frame-pointer" \
    CXXFLAGS="-g -O1 -fno-omit-frame-pointer" \
    LDFLAGS="-lasan -lubsan" \
    ../configure \
      --disable-nls \
      --disable-optimizations \
      --with-sanitizer=address,bounds,shift,integer-divide-by-zero,pointer-overflow,vla-bound \
      --enable-run-as-root \
      --enable-smb2 \
      --enable-vnc \
      --enable-srt \
      --enable-librist \
      --enable-microdns \
      --enable-dav1d \
      --enable-aom \
      --enable-gme \
      --enable-qt \
      --enable-skins2 \
      --disable-realrtsp \
      --disable-live555 \
      --disable-wayland \
      --disable-spatialaudio \
      --disable-projectm \
      --disable-vsxu; \
    make -j"$(nproc)"; \
    make -C test -j"$(nproc)" vlc-demux-run vlc-demux-dec-run

# Static mutation harness. Its built-in module list is deliberately smaller
# than the broad dynamic builds; threat_model.md documents that distinction.
# Same pattern as the harfbuzz and fribidi enrollments and OSS-Fuzz: compile
# everything with -fsanitize=fuzzer-no-link (coverage instrumentation, no
# libFuzzer main), then link only the harness programs with -fsanitize=fuzzer.
# Overriding LDFLAGS for that link is safe: on Linux configure's LDFLAGS carry
# the sanitizer group, -Wl,-z,defs for shared objects, and optional section
# garbage collection and build-id flags, none of which these two static
# executables need.
# VLC's own --with-libfuzzer option is not usable here: it forces
# -fsanitize-coverage=trace-pc-guard, which current libFuzzer rejects at
# startup. Passing -fsanitize=fuzzer through --with-sanitizer would inject
# libFuzzer's main() into every configure link test.
RUN set -eux; \
    mkdir /src/build-fuzz; \
    cd /src/build-fuzz; \
    CC=clang CXX=clang++ \
    CFLAGS="-g -O1 -fno-omit-frame-pointer -DNDEBUG" \
    CXXFLAGS="-g -O1 -fno-omit-frame-pointer -DNDEBUG" \
    ../configure \
      --disable-nls \
      --disable-optimizations \
      --with-sanitizer=fuzzer-no-link,address \
      --disable-shared \
      --enable-static \
      --disable-vlc \
      --disable-lua \
      --disable-dbus \
      --disable-qt \
      --disable-skins2 \
      --disable-xcb \
      --disable-wayland \
      --disable-realrtsp \
      --disable-live555 \
      --disable-spatialaudio \
      --disable-projectm \
      --disable-vsxu; \
    make -j"$(nproc)"; \
    make -C test -j"$(nproc)" vlc-demux-libfuzzer vlc-demux-dec-libfuzzer \
      LDFLAGS="-fsanitize=fuzzer,address"

ENV ASAN_OPTIONS=abort_on_error=1:allocator_may_return_null=1:detect_leaks=0:symbolize=1 \
    UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=0

# Cheap build-time checks. Leave the complete suites and longer campaigns for
# the offline audit, but prove that both replay and mutation harnesses start.
RUN set -eux; \
    VLC_TARGET=voc /src/build-asan/test/vlc-demux-dec-run \
      /src/test/samples/empty.voc; \
    VLC_TARGET=voc /src/build-fuzz/test/vlc-demux-dec-libfuzzer \
      -runs=1 /src/test/samples/empty.voc

RUN cd /src/build \
    && (timeout 15m make -j2 check \
        || echo "WARNING: VLC tests reported failures or timed out; inspect test-suite.log files")
