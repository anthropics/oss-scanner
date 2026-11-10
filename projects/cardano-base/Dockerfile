# The scanner builds this with the cardano-base checkout as the build context. Network access is available during
# this build and removed afterwards, so everything the tests need is fetched here.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git xz-utils python3 bash procps \
    && rm -rf /var/lib/apt/lists/*

# Nix, taken from the official image (pinned), running single-user as root without a sandbox. IOG's binary cache
# provides GHC and the Haskell dependencies, which would take far longer than the build limit to compile.
COPY --from=nixos/nix:2.28.3 /nix /nix
RUN ln -s /nix/var/nix/profiles/default /root/.nix-profile \
 && mkdir -p /etc/nix \
 && printf '%s\n' \
      'experimental-features = nix-command flakes' \
      'build-users-group =' \
      'sandbox = false' \
      'filter-syscalls = false' \
      'accept-flake-config = true' \
      'allow-import-from-derivation = true' \
      'extra-substituters = https://cache.iog.io' \
      'extra-trusted-public-keys = hydra.iohk.io:f/Ea+s+dFdN+3Y/G+FDgSq+a5NEWhJGzdjvKNGv0/EQ=' \
      > /etc/nix/nix.conf
ENV PATH=/nix/var/nix/profiles/default/bin:$PATH

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch the project's dev shell (GHC, cabal, libsodium-vrf, secp256k1, blst) and save its environment, so it works
# offline without evaluating the flake again. The Debian paths are appended so the scanner's tools stay on PATH.
RUN nix print-dev-env > /etc/cardano-env.sh \
 && echo '. /etc/cardano-env.sh; export PATH="$PATH:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"' >> /root/.bashrc

# Build everything, tests included, as the maintainers do. `cabal update` caches the Hackage and CHaP indexes, so
# later rebuilds work offline.
RUN bash -c '. /etc/cardano-env.sh && cabal update && cabal build all --enable-tests -j'

# Run the tests so you know the image works, but do not let a failing or slow test abort the build.
RUN bash -c '. /etc/cardano-env.sh && (timeout 1200 cabal test all -j || echo "WARNING: cabal test reported failures")'
