# pdf_oxide: a Rust PDF library (parser, text/markdown/HTML extraction,
# renderer, editor, signatures). The scanner builds this with the repository
# checkout as the build context.
#
# The project's release profile is tuned for shipping (fat LTO, one codegen
# unit, stripped), which compiles the whole crate on a single core. For the
# audit it is overridden: parallel codegen, no LTO, and symbols and line
# tables kept so crashes come with readable backtraces. Four jobs keep rustc's
# memory (~2 GB a job on this crate) within a modest VM.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CARGO_TERM_COLOR=never \
    CARGO_BUILD_JOBS=4 \
    CARGO_PROFILE_RELEASE_LTO=false \
    CARGO_PROFILE_RELEASE_CODEGEN_UNITS=16 \
    CARGO_PROFILE_RELEASE_STRIP=false \
    CARGO_PROFILE_RELEASE_DEBUG=line-tables-only \
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

# The `pdf-oxide` command-line driver (extract text / markdown / HTML,
# render, inspect) and, through it, the library with the renderer: one
# compile of pdf_oxide. Never --all-features: `fips` and `legacy-crypto` are
# mutually exclusive.
RUN cargo build --release -p pdf_oxide_cli

# Tests are not built here: they recompile the whole crate in test mode. In
# the image, `cargo test --features rendering --lib` runs the unit tests and
# `cargo test --features rendering --test <name>` one integration test.
