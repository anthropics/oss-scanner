# Gerbil Scheme v0.19 (v0.19-staging): builds the integrated Gambit, Gerbil core, stdlib and tools,
# installs to /opt/gerbil, then runs the test suite (non-fatal, time-bounded).
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git pkg-config python3 \
      libssl-dev zlib1g-dev libsqlite3-dev sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The scanner clones without --recursive: fetch the pinned Gambit submodule ourselves.
RUN git submodule update --init src/gambit

# --enable-march= (empty) instead of the default "native": the image may run on a different CPU than it was built on.
# -g -fno-omit-frame-pointer for usable backtraces in gdb/valgrind.
ENV CFLAGS="-g -fno-omit-frame-pointer"
RUN ./configure --prefix=/opt/gerbil --enable-march= \
    && GERBIL_BUILD_CORES="$(nproc)" make \
    && make install

ENV PATH=/opt/gerbil/bin:$PATH \
    GERBIL_HOME=/opt/gerbil

# Same test invocation as .github/workflows/ci.yml. Bounded at 15 minutes so the 45-minute build budget holds;
# failures only warn.
RUN timeout 900 gxtest -q src/gerbil/test/... src/std/... src/lang/... src/tools/... \
    || echo "WARNING: gxtest reported failures or timed out (exit $?)"
