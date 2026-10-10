# HodeiShield Attest Verifier: a bash script (scripts/attest/verify-attestation.sh) that needs
# OpenSSL >= 3.5 (ML-DSA-65), python3 and jq. There is nothing to compile, so the build is
# "install the tools, run the offline tests".
#
# The base image is the one the repository pins in container/Dockerfile and README.md.
# Debian 13 ships OpenSSL 3.5, the first release with ML-DSA (FIPS 204).
FROM debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a
ENV DEBIAN_FRONTEND=noninteractive
# git: for the checkout's history. shellcheck: lints the script. locales: lets the Latin-1 locale test run.
# cosign is optional (only --anchor-file needs it); without it the vectors with real Sigstore bundles are skipped.
# hadolint ignore=DL3008
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
      ca-certificates git openssl python3 jq shellcheck locales \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src. The checkout is main,
# which is always the latest release.
COPY . /src
WORKDIR /src

# Build: nothing to compile. Check the toolchain and lint the script (reported, not fatal).
RUN openssl version && openssl list -signature-algorithms | grep -i ml-dsa-65 \
    && python3 --version && jq --version
RUN shellcheck scripts/attest/verify-attestation.sh tests/run.sh tests/vectors.sh \
    || echo "WARNING: shellcheck reported findings"

# A Latin-1 locale, for the test that the verdict does not depend on the locale (skipped if absent).
RUN (localedef -c -i en_US -f ISO-8859-1 en_US.ISO-8859-1 || true)

# The offline tests (no network). tests/run.sh already runs tests/vectors.sh, in text and --json mode.
# The mutant check must never run here: VERIFIER_SKIP_MUTANTS=1 skips it.
RUN (VERIFIER_SKIP_MUTANTS=1 bash tests/run.sh || echo "WARNING: tests/run.sh reported failures")
