FROM rust:1.93.0-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_NET_GIT_FETCH_WITH_CLI=true \
    CARGO_NET_RETRY=10 \
    CARGO_INCREMENTAL=0 \
    CARGO_TERM_COLOR=never \
    RUST_BACKTRACE=1 \
    VERGEN_GIT_BRANCH=unknown \
    VERGEN_GIT_SHA=unknown \
    VERGEN_IDEMPOTENT=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash build-essential ca-certificates clang cmake curl git libclang-dev \
      libssl-dev pkg-config python3 \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
RUN bash <<'EOF'
set -euo pipefail
arch="${TARGETARCH:-$(uname -m)}"
case "$arch" in
    arm64|aarch64) asset=solc-static-linux-arm ;;
    amd64|x86_64) asset=solc-static-linux ;;
    *) echo "unsupported architecture: $arch" >&2; exit 1 ;;
esac
base=https://github.com/ethereum/solidity/releases/download
curl -fsSL --retry 5 --retry-all-errors --retry-connrefused --connect-timeout 30 \
    -o /usr/local/bin/solc-0.8.31 "$base/v0.8.31/$asset"
curl -fsSL --retry 5 --retry-all-errors --retry-connrefused --connect-timeout 30 \
    -o /usr/local/bin/solc-0.8.20 "$base/v0.8.20/$asset"
chmod +x /usr/local/bin/solc-0.8.31 /usr/local/bin/solc-0.8.20
cat > /usr/local/bin/solc <<'SCRIPT'
#!/bin/sh
for arg in "$@"; do
    case "$arg" in
        *sp1-contracts*|*v6.1.0*)
            exec /usr/local/bin/solc-0.8.20 "$@"
            ;;
    esac
done
exec /usr/local/bin/solc-0.8.31 "$@"
SCRIPT
chmod +x /usr/local/bin/solc
solc --version
solc-0.8.20 --version
EOF

COPY . /src
WORKDIR /src

ENV COMPILE_CONTRACTS=true \
    CARGO_TARGET_DIR=/src/target

RUN cargo fetch --locked \
    && cargo fetch --locked --manifest-path tooling/Cargo.toml

RUN make -C tooling/ef_tests/blockchain download-test-vectors

RUN bash <<'EOF'
set -euo pipefail

root=/opt/ethrex-git
work=/tmp/ethrex-contract-vendor
hosts=/tmp/ethrex-git-hosts
mkdir -p "$root" "$work"
: > "$hosts"

mirror_path() {
    local url=$1 key
    key="${url#https://}"
    key="${key#http://}"
    key="${key#git://}"
    key="${key#ssh://git@}"
    key="${key#git@}"
    key="${key//:/\/}"
    printf '%s/%s\n' "$root" "$key"
}

register_host() {
    local url=$1 rest scheme
    case "$url" in
        git@*)
            rest=${url#git@}
            printf 'git@ %s\n' "${rest%%:*}" >> "$hosts"
            ;;
        ssh://*)
            rest=${url#ssh://git@}
            printf 'ssh %s\n' "${rest%%/*}" >> "$hosts"
            ;;
        *://*)
            scheme=${url%%://*}
            rest=${url#*://}
            printf '%s %s\n' "$scheme" "${rest%%/*}" >> "$hosts"
            ;;
        *)
            echo "unsupported dependency URL: $url" >&2
            return 1
            ;;
    esac
}

ensure_mirror() {
    local url=$1 path
    path=$(mirror_path "$url")
    if [[ ! -d "$path" ]]; then
        mkdir -p "$(dirname "$path")"
        git clone --mirror "$url" "$path"
    fi
    register_host "$url"
    printf '%s\n' "$path"
}

vendor_submodules() {
    local checkout=$1 url sha path
    git -C "$checkout" submodule foreach --recursive --quiet \
        'printf "%s %s\n" "$(git remote get-url origin)" "$sha1"' |
    while read -r url sha; do
        path=$(ensure_mirror "$url")
        git -C "$path" fetch "$url" "$sha:refs/heads/ethrex-pins/$sha"
        git -C "$path" branch -f ethrex-vendored "$sha"
        git -C "$path" symbolic-ref HEAD refs/heads/ethrex-vendored
    done
}

vendor_repo() {
    local url=$1 branch=$2 sha=$3 recursive=$4 path name checkout
    path=$(ensure_mirror "$url")
    git -C "$path" branch -f "$branch" "$sha"
    git -C "$path" symbolic-ref HEAD "refs/heads/$branch"
    name=$(basename "$path" .git)
    checkout="$work/$name"
    git clone "$url" "$checkout"
    git -C "$checkout" checkout --detach "$sha"
    if [[ "$recursive" == true ]]; then
        git -C "$checkout" submodule update --init --recursive
        vendor_submodules "$checkout"
    fi
}

vendor_repo https://github.com/OpenZeppelin/openzeppelin-contracts-upgradeable.git \
    release-v5.4 e725abddf1e01cf05ace496e950fc8e243cc7cab true
vendor_repo https://github.com/OpenZeppelin/openzeppelin-contracts.git \
    release-v4.9 dc44c9f1a4c3b10af99492eed84f83ed244203f6 true
vendor_repo https://github.com/succinctlabs/sp1-contracts.git \
    ethrex-vendored 2ac5ecbbe473421a963d67e55f182e9a36576f7c false
vendor_repo https://github.com/pcaversaccio/create2deployer \
    ethrex-vendored b3521e52ce800f1c2824e85b8da87164fcabfac4 true

test -f "$work/sp1-contracts/contracts/src/v6.1.0/SP1VerifierGroth16.sol"

while read -r scheme host; do
    case "$scheme" in
        https|http|git)
            git config --system "url.file://$root/$host/.insteadOf" "$scheme://$host/"
            ;;
        ssh)
            git config --system "url.file://$root/$host/.insteadOf" "ssh://git@$host/"
            ;;
        git@)
            git config --system "url.file://$root/$host/.insteadOf" "git@$host:"
            ;;
    esac
done < <(sort -u "$hosts")

rm -rf "$work" "$hosts"

export GIT_ALLOW_PROTOCOL=file
test "$(git ls-remote https://github.com/OpenZeppelin/openzeppelin-contracts-upgradeable.git refs/heads/release-v5.4 | cut -f1)" = e725abddf1e01cf05ace496e950fc8e243cc7cab
test "$(git ls-remote https://github.com/OpenZeppelin/openzeppelin-contracts.git refs/heads/release-v4.9 | cut -f1)" = dc44c9f1a4c3b10af99492eed84f83ed244203f6
test "$(git ls-remote https://github.com/succinctlabs/sp1-contracts.git HEAD | cut -f1)" = 2ac5ecbbe473421a963d67e55f182e9a36576f7c
test "$(git ls-remote https://github.com/pcaversaccio/create2deployer HEAD | cut -f1)" = b3521e52ce800f1c2824e85b8da87164fcabfac4
EOF

RUN cargo fetch --locked --manifest-path /usr/local/cargo/registry/src/index.crates.io-1949cf8c6b5b557f/sp1-core-machine-5.2.4/Cargo.toml \
    && cargo fetch --locked --manifest-path /usr/local/cargo/registry/src/index.crates.io-1949cf8c6b5b557f/sp1-recursion-core-5.2.4/Cargo.toml

ENV CARGO_NET_OFFLINE=true \
    GIT_ALLOW_PROTOCOL=file

RUN cargo build --locked --profile release --bin ethrex --features l2,l2-sql \
    && cargo test --locked --profile release -p ethrex-guest-program --no-default-features --no-run \
    && cargo test --locked --profile release -p ethrex-l2 --lib --no-run \
    && cargo test --locked --profile release --manifest-path tooling/Cargo.toml \
        -p ef_tests-blockchain --no-run \
    && cargo test --locked --profile release --manifest-path tooling/Cargo.toml \
        -p ef_tests-blockchain --features stateless --no-run
