# Scanner image for https://github.com/payjoin/rust-payjoin (master): the payjoin, payjoin-cli and payjoin-mailroom
# crates, built and tested with the latest stable Rust and Cargo-recent.lock as CI's stable job does.
FROM rust:1-trixie

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Override rust-toolchain.toml, which pins a nightly, with the stable toolchain in this image. Line tables only keep
# files and lines in backtraces while the target directory stays a few GB.
ENV RUSTUP_TOOLCHAIN=${RUST_VERSION} \
    RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never \
    CARGO_PROFILE_DEV_DEBUG=line-tables-only

# Fetch every crate the lockfile names, so later builds stay offline.
RUN cp Cargo-recent.lock Cargo.lock && cargo fetch --locked
ENV CARGO_NET_OFFLINE=true

# A step that fails fails the build, and primary_contact gets the log. This also downloads the bitcoind binary that the
# integration tests run, through the build script of the bitcoind crate.
RUN cargo test --locked --package payjoin --package payjoin-cli --package payjoin-mailroom --all-features --no-run

# Show in the build log that the tests run, without failing the build on a broken or flaky test. NGINX_EXE stays unset,
# so the payjoin-mailroom tests that need an nginx with stream support built in skip themselves.
RUN timeout --kill-after=5 1200 cargo test --locked --package payjoin --package payjoin-cli \
      --package payjoin-mailroom --all-features || echo "WARNING: cargo test reported failures"
