# Scanner image for https://github.com/lightningdevkit/rust-lightning (main): the LDK workspace crates, built and
# tested with the latest stable Rust as CI's workspace job does.
FROM rust:1-trixie

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Line tables only keep files and lines in backtraces while the target directory stays a few GB.
ENV RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never \
    CARGO_PROFILE_DEV_DEBUG=line-tables-only

# No lockfile is committed, so resolve one as CI does and fetch every crate it names, so later builds stay offline.
RUN cargo fetch
ENV CARGO_NET_OFFLINE=true

# A step that fails fails the build, and primary_contact gets the log.
RUN cargo test --no-run

# Show in the build log that the tests run, without failing the build on a broken or flaky test.
RUN timeout --kill-after=5 1200 cargo test || echo "WARNING: cargo test reported failures"
