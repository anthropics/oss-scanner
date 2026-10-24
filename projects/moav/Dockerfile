# OSS Scanner build for MoaV (MotherofallVPNs/MoaV).
#
# MoaV is a Bash + Docker Compose orchestration (install.sh, moav.sh, lib/*.sh, scripts/, dockerfiles/,
# configs/, templates/), not a single compiled artifact. A full `moav build` spins up ~25 protocol
# containers and needs a live Docker daemon, which is not available during an isolated image build.
# So this Dockerfile does what is meaningful for static analysis: it installs MoaV's host toolchain,
# places the full checkout at /src for the scanner to read, and syntax-validates every shell script as
# the build step. The security value is in auditing MoaV's own orchestration/config-generation code.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git bash shellcheck python3 jq curl openssl qrencode coreutils findutils grep sed gawk \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# "Build" = validate the shell sources. bash -n must pass (a parse error fails the build and emails the log).
RUN set -eu; \
    find . -type f \( -name '*.sh' -o -name 'moav.sh' -o -name 'install.sh' \) -not -path './.git/*' -print0 \
      | xargs -0 -r -n1 bash -n

# shellcheck is advisory: surface findings in the build log but never abort the build.
RUN find . -type f \( -name '*.sh' -o -name 'moav.sh' -o -name 'install.sh' \) -not -path './.git/*' -print0 \
      | xargs -0 -r shellcheck -S warning || echo "WARNING: shellcheck reported findings (non-fatal)"
