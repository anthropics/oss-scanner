# Litecoin Core (master: the 0.21.5.x release line, Bitcoin Core 0.21 plus MWEB), built two ways, both out of tree,
# without the GUI and the benchmarks:
#   /src/build       like a release: GCC, -O2 -g, wallet (BDB and SQLite), ZMQ and UPnP compiled in
#   /src/build_asan  the same sources with clang and AddressSanitizer + UndefinedBehaviorSanitizer, to run a reproducer
#                    against an instrumented node
# ccache keeps the objects of both builds, so returning to the scanned revision after a checkout or patch is quick.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUTF8=1 \
    CCACHE_DIR=/ccache \
    CCACHE_MAXSIZE=10G

# libfmt is required by libmw. miniupnpc must stay below 2.2.8 (Ubuntu 24.04 has 2.2.6) and Boost below 1.85
# (24.04 has 1.83) for this tree to build.
RUN apt-get update && apt-get install -y --no-install-recommends \
      autoconf automake bsdextrautils bsdmainutils build-essential ca-certificates ccache git libtool pkg-config \
      clang-18 libclang-rt-18-dev llvm-18 \
      libboost-dev libboost-filesystem-dev libboost-system-dev libboost-test-dev libboost-thread-dev \
      libdb5.3++-dev libevent-dev libfmt-dev libminiupnpc-dev libsqlite3-dev libssl-dev libzmq3-dev \
      python3 python3-venv python3-zmq \
    && rm -rf /var/lib/apt/lists/*

# The functional test framework imports blake3 (MWEB hashes), which Ubuntu does not package. Pinned so that the image
# does not change under us.
RUN python3 -m venv --system-site-packages /opt/litecoin-test-env \
    && /opt/litecoin-test-env/bin/pip install --no-cache-dir blake3==1.0.8
ENV PATH="/opt/litecoin-test-env/bin:${PATH}"

# Sanitizer settings for /src/build_asan, as in the tree's CI, with the UBSan suppressions extended below.
ENV ASAN_OPTIONS=detect_stack_use_after_return=1:check_initialization_order=1:strict_init_order=1 \
    LSAN_OPTIONS=suppressions=/src/test/sanitizer_suppressions/lsan \
    UBSAN_OPTIONS=suppressions=/etc/litecoin-ubsan.supp:print_stacktrace=1:halt_on_error=1:report_error_type=1 \
    ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18 \
    UBSAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18 \
    LLVM_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The tree's UBSan suppressions, plus two known reports that would otherwise halt every instrumented node: mio's
# basic_mmap moves an uninitialised bool (LeafSet::Flush, on every MWEB leafset flush), and crc32c's arm64 code does
# misaligned loads (only when this image is built on arm64).
RUN { cat /src/test/sanitizer_suppressions/ubsan \
      && printf 'bool:mio/mmap.hpp\nenum:mio/mmap.hpp\nalignment:crc32c_arm64.cc\n'; } > /etc/litecoin-ubsan.supp

# BDB 4.8, which release builds use, is not packaged; 5.3 with --with-incompatible-bdb is the usual substitute.
# The tree tracks a stale src/secp256k1-zkp/libsecp256k1-config.h (without the extrakeys module) that an out-of-tree
# build would include instead of the one configure generates; -iquote puts the generated one first.
# One compile job per CPU, but at most one per 2 GiB of memory.
RUN ./autogen.sh \
    && jobs=$(nproc) && mem=$(awk '/MemTotal/ {print int($2 / 2097152)}' /proc/meminfo) \
    && if [ "$mem" -ge 1 ] && [ "$mem" -lt "$jobs" ]; then jobs=$mem; fi \
    && mkdir -p /src/build && cd /src/build \
    && ../configure --without-gui --disable-bench --with-incompatible-bdb --enable-zmq \
         CPPFLAGS="-iquote /src/build/src/secp256k1-zkp/src" \
         CC=gcc CXX=g++ CFLAGS="-O2 -g -fno-omit-frame-pointer" CXXFLAGS="-O2 -g -fno-omit-frame-pointer" \
    && make -j"$jobs"

RUN jobs=$(nproc) && mem=$(awk '/MemTotal/ {print int($2 / 2097152)}' /proc/meminfo) \
    && if [ "$mem" -ge 1 ] && [ "$mem" -lt "$jobs" ]; then jobs=$mem; fi \
    && mkdir -p /src/build_asan && cd /src/build_asan \
    && ../configure --without-gui --disable-bench --with-incompatible-bdb --enable-zmq \
         --with-sanitizers=address,undefined \
         CPPFLAGS="-iquote /src/build_asan/src/secp256k1-zkp/src" \
         CC=clang-18 CXX=clang++-18 \
         CFLAGS="-O1 -g -fno-omit-frame-pointer" CXXFLAGS="-O1 -g -fno-omit-frame-pointer" \
    && make -j"$jobs" \
    && ccache --show-stats

# Fail the build only on what cannot flake: binaries that start, and the Python modules the tests need.
# LeakSanitizer needs ptrace, which docker build does not allow (the scanner's container does), so it is off here.
RUN python3 -c "import blake3, zmq" \
    && /src/build/src/litecoind -version > /dev/null \
    && ASAN_OPTIONS=detect_leaks=0 /src/build_asan/src/litecoind -version > /dev/null

# Show in the build log that the tests run offline, without failing the build on a broken or flaky test.
RUN jobs=$(nproc) \
    && (cd /src/build && timeout --kill-after=5 900 make -j"$jobs" check || echo "WARNING: make check reported failures") \
    && (timeout --kill-after=5 600 python3 /src/build/test/functional/test_runner.py -j"$jobs" \
          mweb_basic.py mweb_p2p.py mweb_mempool.py mweb_mining.py mweb_reorg.py mweb_weight.py \
          mweb_wallet_basic.py mweb_p2p_mutated_compactblock.py p2p_invalid_messages.py wallet_basic.py \
        || echo "WARNING: functional tests reported failures") \
    && (ASAN_OPTIONS="$ASAN_OPTIONS:detect_leaks=0" timeout --kill-after=5 600 \
          python3 /src/build_asan/test/functional/test_runner.py -j"$jobs" mweb_basic.py mweb_p2p.py \
        || echo "WARNING: functional tests against the sanitizer build reported failures")
