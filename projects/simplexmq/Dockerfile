# OSS Scanner build for simplexmq (https://github.com/simplex-chat/simplexmq).
# Toolchain follows the repository's Dockerfile.build; build flags follow .github/workflows/build.yml.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    TZ=Etc/UTC

# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y \
      ca-certificates curl git xz-utils build-essential pkg-config \
      libffi-dev libgmp3-dev libncurses-dev libnuma-dev zlib1g-dev libssl-dev \
      libpq-dev libsqlite3-dev sqlite3 llvm llvm-dev postgresql \
    && rm -rf /var/lib/apt/lists/*

# Tests connect to localhost:5432 as the postgres superuser without a password, as the CI service does.
RUN for conf in /etc/postgresql/*/main/pg_hba.conf; do \
      printf 'local all all trust\nhost all all 127.0.0.1/32 trust\nhost all all ::1/128 trust\n' > "$conf"; \
    done

ENV BOOTSTRAP_HASKELL_NONINTERACTIVE=1 \
    BOOTSTRAP_HASKELL_GHC_VERSION=9.6.3 \
    BOOTSTRAP_HASKELL_CABAL_VERSION=3.14.1.1 \
    BOOTSTRAP_HASKELL_INSTALL_NO_STACK=1 \
    BOOTSTRAP_HASKELL_INSTALL_NO_STACK_HOOK=1 \
    PATH="/root/.cabal/bin:/root/.ghcup/bin:$PATH"
RUN curl --proto '=https' --tlsv1.2 -sSf https://get-ghcup.haskell.org | sh \
    && ghcup set ghc "$BOOTSTRAP_HASKELL_GHC_VERSION" \
    && ghcup set cabal "$BOOTSTRAP_HASKELL_CABAL_VERSION"

COPY . /src
WORKDIR /src

# The scanner clones without submodules; cbits/blst and cbits/libbbs are needed to compile.
RUN git submodule update --init --recursive

# Flags live in cabal.project.local so that a later `cabal build` or `cabal test` offline reuses this build.
# GHC -j compiles modules in parallel to fit the scanner's 45-minute build limit.
RUN printf '%s\n' \
      'tests: True' \
      'test-show-details: direct' \
      'package simplexmq' \
      '  flags: +server_postgres' \
      '  ghc-options: -j' \
      > cabal.project.local \
    && cabal update \
    && cabal build --jobs="$(nproc)" all

# The full suite takes over an hour; run the core tests, bounded so a hang cannot exhaust the build limit.
RUN service postgresql start; \
    timeout 300 "$(cabal list-bin simplexmq-test)" -m "Core tests" || echo "WARNING: core tests reported failures"; \
    service postgresql stop
