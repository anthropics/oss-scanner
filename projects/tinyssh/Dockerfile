FROM debian:trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CC=gcc \
    CFLAGS="-g -fno-omit-frame-pointer" \
    LC_ALL=C

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash build-essential ca-certificates git openssh-client python3 \
      passwd util-linux lib1305-dev lib25519-dev libntruprime-dev librandombytes-dev \
    && rm -rf /var/lib/apt/lists/*

# SSH integration tests require a non-root account with a Bash login shell.
RUN useradd --create-home --shell /bin/bash scanner-test

# The scanner expects the checkout at /src. The build detects the installed
# external crypto libraries and uses bundled implementations as fallbacks.
COPY . /src
WORKDIR /src

# Supply CFLAGS through the environment to retain each Makefile's own flags,
# including -fwrapv and the appropriate cryptoint include path.
RUN make \
    && make -C tests \
    && chown -R scanner-test:scanner-test /src

# Preserve failed-test output for the scanner without preventing an audit.
RUN runuser -u scanner-test -- make test \
    || echo "WARNING: make test reported failures; inspect /src/tests/*.out"
RUN runuser -u scanner-test -- make test-ssh \
    || echo "WARNING: make test-ssh reported failures; inspect /src/tests/*.out"

# The scanner runs as root, while the test account owns the checkout.
RUN git config --global --add safe.directory /src
