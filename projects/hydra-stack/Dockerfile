# hydra-stack: self-evolving skill system for coding agents. The engine under memory/ is stdlib-only Python 3.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src/memory

# Byte-compile everything so syntax errors fail the build.
RUN python3 -m compileall -q /src/memory

# The test suite uses a temp HOME/DB/vault per test; do not let a failure abort the build.
RUN python3 -I test_hydra_graph.py -v || echo "WARNING: test_hydra_graph.py reported failures"
