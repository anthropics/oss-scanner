# OSS Scanner build of DPDK (main).
#
# Two builds of the same checkout in /src:
#   /src/build       gcc, debugoptimized, all buildable drivers and examples.
#                    Distribution-like; run the unit tests here:
#                      meson test -C /src/build --suite fast-tests
#   /src/build-asan  clang, AddressSanitizer + UBSan, debug, virtual and software
#                    drivers only.
#                    Use it to confirm memory-safety findings.
#
# No hugepages, no NICs and no root-only kernel modules in the scanner, so run
# with virtual devices only, e.g.:
#   /src/build-asan/app/dpdk-testpmd -l 0-1 --no-huge -m 512 --no-pci \
#       --vdev net_pcap0,rx_pcap=crafted.pcap,tx_pcap=/tmp/out.pcap -- -i
#
# -Dplatform=generic so the image does not depend on the build host CPU.
FROM ubuntu:26.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential clang libclang-rt-dev llvm lld \
      meson ninja-build pkg-config python3 python3-pyelftools \
      libnuma-dev libpcap-dev libssl-dev zlib1g-dev libelf-dev \
      libbpf-dev libxdp-dev libarchive-dev libjansson-dev libibverbs-dev \
      libisal-dev libipsec-mb-dev libfdt-dev libbsd-dev \
      gdb tcpdump python3-scapy iproute2 file xxd less \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# 1) Reference build
RUN meson setup /src/build /src \
      --buildtype=debugoptimized \
      -Dplatform=generic \
      -Dc_args="-fno-omit-frame-pointer" \
      -Dexamples=all \
      -Denable_docs=false \
    && meson compile -C /src/build

# 2) Sanitizer build; clang needs b_lundef=false with -fsanitize.
#    Only drivers that can run without hardware: hardware is trusted and
#    cannot be exercised here, and some hardware drivers need >8G per
#    compiler process under ASan+UBSan.
#    alignment and function checks are disabled: unaligned header loads and
#    callback casts are deliberate and would drown real reports.
RUN CC=clang meson setup /src/build-asan /src \
      --buildtype=debug \
      -Dplatform=generic \
      -Db_sanitize=address,undefined \
      -Db_lundef=false \
      -Dc_args="-fno-omit-frame-pointer -fno-sanitize=alignment,function" \
      -Denable_drivers=bus/pci,bus/vdev,mempool/ring,mempool/stack,net/null,net/ring,net/pcap,net/af_packet,net/af_xdp,net/tap,net/memif,net/vhost,net/virtio,net/bonding,crypto/null,crypto/openssl,crypto/ipsec_mb,crypto/scheduler,crypto/virtio,compress/isal,compress/zlib,event/sw,baseband/null,dma/skeleton \
      -Denable_docs=false \
    && meson compile -C /src/build-asan

ENV ASAN_OPTIONS=detect_leaks=0:abort_on_error=1:symbolize=1 \
    UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=0

# Smoke tests; a failure must not abort the image build.
RUN meson test -C /src/build --no-rebuild --suite fast-tests \
      --timeout-multiplier 3 --num-processes 2 \
    || echo "WARNING: fast-tests reported failures"
