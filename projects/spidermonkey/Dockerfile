# OSS Scanner build of the SpiderMonkey JS shell.
#
# What is built: debug+optimized JS shell with AddressSanitizer, at /obj-asan/dist/bin/js.

FROM ubuntu:26.04
ENV DEBIAN_FRONTEND=noninteractive \
    MOZBUILD_STATE_PATH=/mozbuild \
    MOZCONFIG=/mozconfig-asan \
    ASAN_OPTIONS=detect_leaks=0:allocator_may_return_null=1 \
    ASAN_SYMBOLIZER_PATH=/mozbuild/clang/bin/llvm-symbolizer

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git python3 python3-pip python3-venv build-essential unzip \
        gdb strace less vim \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN printf '%s\n' \
      'ac_add_options --enable-project=js' \
      'ac_add_options --enable-debug' \
      'ac_add_options --enable-optimize' \
      'ac_add_options --disable-tests' \
      'ac_add_options --enable-address-sanitizer' \
      'ac_add_options --disable-jemalloc' \
      'ac_add_options --enable-rust-simd' \
      'ac_add_options --enable-debug-symbols' \
      'mk_add_options MOZ_OBJDIR=/obj-asan' \
    > "$MOZCONFIG"

RUN ./mach --no-interactive bootstrap --application-choice=js

RUN ./mach build \
    && /obj-asan/dist/bin/js --fuzzing-safe -e 'print("shell ok")'
