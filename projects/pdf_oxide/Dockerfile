# pdf_oxide: a Rust PDF library (parser, text/markdown/HTML extraction,
# renderer, editor, signatures). The scanner builds this with the repository
# checkout as the build context.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_TERM_COLOR=never \
    CARGO_PROFILE_RELEASE_DEBUG=1 \
    RUSTFLAGS="-C force-frame-pointers=yes"
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential clang pkg-config git python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every dependency now; the audit runs offline. The fuzz crate is
# outside the workspace, so it is fetched on its own.
RUN cargo fetch && (cd fuzz && cargo fetch)

# The library with the renderer, and the `pdf-oxide` command-line driver
# (pdf_oxide_cli: extract text / markdown / HTML, render, inspect).
# Never --all-features: `fips` and `legacy-crypto` are mutually exclusive.
RUN cargo build --release -p pdf_oxide --features rendering \
    && cargo build --release -p pdf_oxide_cli

# The unit tests are the cheap check that the image works; they do not abort
# the build. (The integration suite under tests/ is large; build individual
# tests with `cargo test --features rendering --test <name>`.)
RUN (cargo test --release -p pdf_oxide --features rendering --lib \
     || echo "WARNING: unit tests reported failures")
