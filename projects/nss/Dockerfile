# OSS Scanner build of NSS (Network Security Services).
#
# The scanner builds this with the NSS git checkout as the build context, so `COPY . /src` puts NSS at /src.
# Network access exists only while this file builds; the scan that follows runs offline on a small machine
# (2 CPUs, 8 GB), so everything the agent might need (NSPR, Python packages, analysis tools) is fetched here.
#
# What is built: ONE NSS debug build with AddressSanitizer and UndefinedBehaviorSanitizer, the same configuration
# as NSS's own CI job "linux-x64-asan/debug". Output lands in /dist/Debug: libraries in lib/, tools and test
# binaries (certutil, tstclnt, selfserv, ssl_gtest, ...) in bin/. The ssl gtests run once at the end as a smoke
# check; a failure there is reported but does not fail the image build.
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive

# LLVM/Clang 18. Ubuntu 22.04's packaged clang (14) is too old for the sanitizer builds NSS CI uses, so install
# from the official LLVM apt repository, and put unversioned names in /usr/local/bin. That directory precedes
# /usr/bin in PATH, so these keep winning even after the scanner's own layer installs the distro clang.
RUN apt-get update \
    && apt-get -y install --no-install-recommends ca-certificates curl gnupg \
    && curl -fsSL https://apt.llvm.org/llvm-snapshot.gpg.key | gpg --dearmor -o /usr/share/keyrings/llvm.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/llvm.gpg] https://apt.llvm.org/jammy/ llvm-toolchain-jammy-18 main" \
        > /etc/apt/sources.list.d/llvm-18.list \
    && apt-get update \
    && apt-get -y install --no-install-recommends \
        clang-18 clang-format-18 clang-tidy-18 clang-tools-18 \
        lld-18 lldb-18 libclang-18-dev libclang-rt-18-dev libfuzzer-18-dev \
        llvm-18 llvm-18-dev \
    && for tool in clang clang++ clang-format clang-tidy clang-cpp lld lldb clangd scan-build \
                   asan_symbolize llvm-symbolizer llvm-ar llvm-nm llvm-objdump llvm-ranlib llvm-strip \
                   llvm-profdata llvm-cov; do \
        ln -sf "/usr/bin/${tool}-18" "/usr/local/bin/${tool}"; \
    done \
    && rm -rf /var/lib/apt/lists/*

# GCC 14 from the Ubuntu toolchain PPA (22.04 ships GCC 11), as a second compiler to cross-check with.
RUN apt-get update \
    && apt-get -y install --no-install-recommends software-properties-common \
    && add-apt-repository -y ppa:ubuntu-toolchain-r/test \
    && apt-get update \
    && apt-get -y install --no-install-recommends gcc-14 g++-14 \
    && update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-14 140 --slave /usr/bin/g++ g++ /usr/bin/g++-14 \
    && rm -rf /var/lib/apt/lists/*

# Build tools NSS needs (gyp, ninja, zlib, sqlite, mercurial for anything that still speaks hg), debuggers and
# analysers from the dev container (gdb, valgrind, cppcheck, bear, lcov, AFL++, the Z3 CLI and headers), and the
# PyYAML that NSS's ./mach imports.
RUN apt-get update \
    && apt-get -y install --no-install-recommends \
        build-essential cmake ninja-build gyp pkg-config \
        python3 python3-distutils python3-yaml python3-pip python3-venv pipx \
        zlib1g-dev libsqlite3-dev sqlite3 \
        git mercurial perl \
        gdb valgrind cppcheck lcov bear strace ltrace file xxd jq \
        afl++ z3 libz3-dev \
        psmisc procps vim tmux less \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -c "import yaml; print('PyYAML', yaml.__version__)"

# git-cinnabar: lets git talk to NSS's canonical Mercurial repository and to hg.mozilla.org generally.
RUN curl -sL "https://github.com/glandium/git-cinnabar/releases/download/0.7.3/git-cinnabar.linux.x86_64.tar.xz" \
    | tar -xJ --strip-components=1 -C /usr/local/bin/ \
    && git cinnabar --version

# Rust, used here to build weggli (semantic C/C++ code search).
ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH="/usr/local/cargo/bin:$PATH"
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path \
    && cargo install weggli \
    && weggli --version

# Python analysis libraries (angr, z3-solver, tlslite-ng) in one uv-managed venv on Python 3.12: angr needs
# >= 3.12 and the system python3 is 3.10, which must stay as it is for ./mach and every `#!/usr/bin/env python3`
# script in NSS. The venv is reached through the wrapper scripts analysis-python / angr-python / tlslite-python
# (wrappers, not symlinks: CPython finds pyvenv.cfg relative to the path it was invoked by). Installing here
# also warms uv's cache, so `uv run --no-project --with angr script.py` works offline later.
ENV UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_CACHE_DIR=/opt/uv/cache
RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh \
    && uv python install 3.12 \
    && uv venv --python 3.12 /opt/venvs/analysis \
    && uv pip install --python /opt/venvs/analysis/bin/python angr z3-solver tlslite-ng \
    && for name in analysis-python angr-python tlslite-python; do \
        printf '#!/bin/sh\nexec /opt/venvs/analysis/bin/python "$@"\n' > "/usr/local/bin/$name"; \
        chmod 0755 "/usr/local/bin/$name"; \
    done \
    && analysis-python -c "import angr, z3, tlslite"

# Python applications via pipx: semgrep (pattern-based static analysis), diff-cover, and Sphinx with myst-parser,
# which NSS's `./mach doc-lint` needs (doc/src is MyST Markdown).
ENV PIPX_HOME=/opt/pipx \
    PIPX_BIN_DIR=/usr/local/bin
RUN pipx install semgrep \
    && pipx install diff-cover \
    && pipx install sphinx \
    && pipx inject sphinx myst-parser \
    && semgrep --version && diff-cover --version && sphinx-build --version

# The environment NSS's own CI uses for its ASan/UBSan job (taskcluster/kinds/build/linux.yml and
# taskcluster/nss_taskgraph/transforms/build.py), plus HOST/DOMSUF, which tests/all.sh needs to mint the server
# certificate and which NSS's CI images also hard-code. DIST is read by build.sh, ./mach and tests/all.sh.
ENV CC=clang \
    CXX=clang++ \
    CCC=clang++ \
    ASAN_OPTIONS=allocator_may_return_null=1:detect_stack_use_after_return=1 \
    UBSAN_OPTIONS=print_stacktrace=1 \
    NSS_DISABLE_ARENA_FREE_LIST=1 \
    NSS_DISABLE_UNLOAD=1 \
    HOST=localhost \
    DOMSUF=localdomain \
    DIST=/dist

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# NSPR, which build.sh expects beside the checkout, at ../nspr (= /nspr). Full clone so its history is there too.
RUN git clone https://github.com/mozilla/nspr /nspr \
    && git -C /nspr log -1 --format='NSPR is at %h %s (%cs)'

# The build: debug + ASan + UBSan, as NSS CI's "linux-x64-asan/debug" job builds it. A failing step here fails the
# image, and primary_contact gets the log.
RUN ./build.sh --dist="$DIST" --python=python3 --asan --ubsan \
    && ls "$DIST"/Debug/bin/ssl_gtest "$DIST"/Debug/lib/libssl3.so

# Smoke check: a minimal slice of the ssl gtests, as a basic functionality test. GTESTFILTER (read by
# tests/ssl_gtests/ssl_gtests.sh) keeps it to one plain handshake per protocol version: TlsConnectGeneric.Connect
# over TLS 1.0-1.3 and DTLS 1.0-1.3. This also builds the test certificate database at
# /tests_results/security/*/ssl_gtests, which the full ssl_gtest binary can reuse. Bounded, and a failure is only
# reported, so a flaky test does not take the image down with it.
RUN cd /src/tests \
    && (NSS_CYCLES=standard NSS_TESTS=ssl_gtests GTESTFILTER='*/TlsConnectGeneric.Connect/*' timeout 900 ./all.sh \
        || echo "WARNING: ssl_gtests reported failures (or timed out); see /tests_results")

# Final assertion against the finished image. Each layer's own check only proves a tool worked when it was
# installed; this one fails the build if what the agent actually gets is broken.
RUN set -eu; \
    fail() { echo "ENVIRONMENT ASSERTION FAILED: $*" >&2; exit 1; }; \
    [ "$(command -v python3)" = /usr/bin/python3 ] || fail "python3 is not /usr/bin/python3"; \
    python3 -c "import yaml" || fail "system python3 cannot import yaml (needed by ./mach)"; \
    clang --version | head -1 | grep -q ' 18\.' || fail "clang is not version 18"; \
    printf '#include <stdio.h>\nint main(void){puts("ok");return 0;}\n' > /tmp/t.c; \
    clang -g -fsanitize=address,undefined -o /tmp/t /tmp/t.c && /tmp/t > /dev/null || fail "clang cannot build an ASan+UBSan binary"; \
    rm -f /tmp/t /tmp/t.c; \
    for py in analysis-python angr-python tlslite-python; do \
        "$py" -c "import angr, z3, tlslite" || fail "$py cannot import the analysis venv"; \
    done; \
    /opt/pipx/venvs/sphinx/bin/python -c "import myst_parser" || fail "sphinx venv is missing myst-parser"; \
    for tool in gyp ninja gcc g++ gdb valgrind cppcheck bear lcov afl-fuzz z3 semgrep diff-cover sphinx-build \
                weggli uv cargo rustc git hg git-cinnabar; do \
        command -v "$tool" > /dev/null || fail "$tool is not on PATH"; \
    done; \
    for bin in ssl_gtest pk11_gtest certutil tstclnt selfserv pk12util vfychain; do \
        [ -x "$DIST/Debug/bin/$bin" ] || fail "$DIST/Debug/bin/$bin is missing"; \
    done; \
    db="$(mktemp -d)"; export LD_LIBRARY_PATH="$DIST/Debug/lib"; \
    "$DIST/Debug/bin/certutil" -N -d "$db" --empty-password || fail "certutil cannot create a database"; \
    "$DIST/Debug/bin/ssl_gtest" -d "$db" --gtest_list_tests > /dev/null \
        || fail "ssl_gtest does not run against $DIST/Debug/lib"; \
    rm -rf "$db"; \
    echo "all environment assertions passed"
