# bark: the Ark server (captaind, watchmand) and the Ark wallet (bark, barkd).
#
# Upstream builds and tests bark through the repository's nix flake, so this
# image does the same. The flake pins the daemons that the integration tests
# start as real processes: bitcoind 31.0, Core Lightning 26.06.6 with the hold
# plugin, and PostgreSQL 17. All of it is fetched here, while the network is
# up. The audit that follows runs offline against a warm nix store and a warm
# cargo registry.
#
# Two things you must know to run anything in this image. Both are repeated in
# threat_model.md:
#   * The toolchain is not on the default PATH. Use `bark-run <command>`, or
#     source /opt/bark-env.sh first.
#   * Run the integration tests as the unprivileged user `bark`. They start
#     PostgreSQL, and initdb refuses to run as root. `bark-run` does this.

FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git xz-utils \
    && rm -rf /var/lib/apt/lists/*

# nix runs single-user, owned by `bark`, so the build never needs a daemon.
RUN useradd --create-home --shell /bin/bash bark \
 && mkdir -p /nix /opt/cargo /opt/nix-profiles \
 && chown -R bark:bark /nix /opt

# HOME and USER are set by hand: a USER directive does not set either, and the
# nix installer places the profile by both of them.
ENV CARGO_HOME=/opt/cargo \
    PATH=/home/bark/.nix-profile/bin:$PATH \
    HOME=/home/bark \
    USER=bark

USER bark
WORKDIR /home/bark

# Pinned, not `curl https://nixos.org/nix/install | sh`: that URL redirects to
# whatever release is current, and the installer checks its own tarball against
# a hash it carries, so the script itself is the trust anchor. This hash is the
# one upstream publishes at releases.nixos.org/nix/nix-2.35.2/install.sha256,
# and the one bark pins in .gitlab/images/tests/Dockerfile.
ARG NIX_VERSION=2.35.2
ARG NIX_INSTALLER_SHA256=9adda97297d9e8ab360df95c729eabff4f4f93d6db091953c3a68f29e3fb130c
RUN curl -fsSL -o /tmp/nix-install "https://releases.nixos.org/nix/nix-${NIX_VERSION}/install" \
 && echo "${NIX_INSTALLER_SHA256}  /tmp/nix-install" | sha256sum -c - \
 && sh /tmp/nix-install --no-daemon \
 && rm -f /tmp/nix-install

# bark.cachix.org holds the flake's heavy derivations. Without it this build
# compiles bitcoind, Core Lightning and two electrs forks from source.
RUN mkdir -p /home/bark/.config/nix \
 && printf '%s\n' \
      'experimental-features = nix-command flakes' \
      'accept-flake-config = true' \
      'extra-substituters = https://bark.cachix.org' \
      'extra-trusted-public-keys = bark.cachix.org-1:Iaihe4ABbOQz1CHBoYUZS/sHVAcISasJZ+lL3I4gRB0=' \
      > /home/bark/.config/nix/nix.conf

# scanner contract: the checkout lives inside the image, at /src
COPY --chown=bark:bark . /src
WORKDIR /src

# Copy every flake input into the store, so later evaluation needs no network.
# `path:` rather than a git ref: it does not care whether .git came along, and
# it does not quietly ignore a file the scanner left untracked.
RUN nix flake archive "path:/src"

# Build the dev shell and keep it as a GC root.
RUN nix develop --profile /opt/nix-profiles/bark-dev "path:/src" --command true

# Record the dev shell environment for offline use. It is deliberately not made
# image-wide: LD_LIBRARY_PATH inside it points at the nix glibc and openssl,
# which breaks binaries that came from the base image or from a later layer.
RUN nix develop /opt/nix-profiles/bark-dev --command bash -c 'export -p' \
    | sed -n 's/^declare -x /export /p' \
    | grep -vE '^export (HOME|USER|LOGNAME|PWD|OLDPWD|SHLVL|TMPDIR|TEMP|TMP|SHELL|HOSTNAME|TERM|_)=' \
    > /opt/bark-env.sh

# The integration harness reads the daemon paths from the environment, and the
# justfile is what normally exports them. Tests run here through plain cargo,
# so add them by hand. Keep in sync with the exports at the top of justfile.
RUN . /opt/bark-env.sh \
 && T="$(cargo metadata --format-version 1 --no-deps | jq -r .target_directory)" \
 && printf '%s\n' \
      "export CAPTAIND_EXEC=$T/debug/captaind" \
      "export WATCHMAND_EXEC=$T/debug/watchmand" \
      "export BARK_EXEC=$T/debug/bark-legacy" \
      "export BARK_CLIENT_EXEC=$T/debug/bark-cli" \
      "export BARKD_EXEC=$T/debug/barkd" \
      "export BITCOIND_SNAPSHOT_DIR=/src/test/_bitcoind_snapshot" \
    >> /opt/bark-env.sh

# Warm the cargo registry, then build, so that the offline audit has the
# binaries and the compiled integration harness. These two are the project's
# own commands: `just build-bins` is the first, and the integration recipes
# depend on it. A failure here should fail the build.
RUN . /opt/bark-env.sh && cargo fetch --locked
RUN . /opt/bark-env.sh && cargo build --workspace --bins
RUN . /opt/bark-env.sh && cargo build -p ark-testing --tests

# Cheap tests, so that a broken image shows up here rather than in a report. A
# failing test must not fail the build. ark-testing is excluded because it is
# the integration suite, which starts real daemons and takes much longer.
RUN . /opt/bark-env.sh \
 && (cargo nextest run --no-fail-fast --workspace --exclude ark-testing \
     || echo "WARNING: unit tests reported failures")

# One integration target, as a smoke test. `core` starts bitcoind, Core
# Lightning and the PID locks and does nothing else, so it is the cheapest
# proof that the pinned daemons run in this image with the network removed.
RUN . /opt/bark-env.sh \
 && (cargo nextest run --no-fail-fast -p ark-testing --test core \
     || echo "WARNING: core integration smoke test reported failures")

USER root

# Nothing in the build environment is on the default PATH, and the tests cannot
# run as root, so give both a single entry point.
RUN { echo '#!/bin/bash'; \
      echo '# Run a command in the bark build environment, as the unprivileged'; \
      echo '# user bark. The integration tests start PostgreSQL, and initdb'; \
      echo '# refuses to run as root.'; \
      echo '#   bark-run cargo nextest run -p ark-testing --test bark'; \
      echo '#   bark-run bash -i'; \
      echo 'set -euo pipefail'; \
      echo 'exec setpriv --reuid=bark --regid=bark --init-groups /bin/bash -c '\''export HOME=/home/bark; . /opt/bark-env.sh; cd /src; exec "$@"'\'' bark-run "$@"'; \
    } > /usr/local/bin/bark-run \
 && chmod 0755 /usr/local/bin/bark-run

# Hand the image back as root owns it, so that a later layer installing into
# $HOME does not write into the build user's home.
ENV HOME=/root \
    USER=root

# The audit has no network. Make cargo say so instead of hanging on crates.io.
ENV CARGO_NET_OFFLINE=true
WORKDIR /src
