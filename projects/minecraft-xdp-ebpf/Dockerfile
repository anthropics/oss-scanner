# Scanner image for https://github.com/Outfluencer/Minecraft-XDP-eBPF.
# Mirrors .github/workflows/rust.yml: LLVM from apt.llvm.org (clang compiles xdp/ to BPF in build.rs and the C unit
# tests natively with ASan/UBSan), libbpf headers, gcc-multilib for <asm/types.h> under -target bpf, and stable Rust.
FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl wget gnupg lsb-release software-properties-common git \
      build-essential gcc-multilib pkg-config libbpf-dev python3 \
    && rm -rf /var/lib/apt/lists/*

# The LLVM major version CI uses; clang, llvm-strip and llvm-objdump are made the defaults as in CI.
ARG LLVM_VERSION=23
RUN wget -qO /tmp/llvm.sh https://apt.llvm.org/llvm.sh \
    && bash /tmp/llvm.sh "${LLVM_VERSION}" all \
    && rm /tmp/llvm.sh \
    && for tool in clang clang++ llvm-strip llvm-objdump; do \
         update-alternatives --install "/usr/bin/$tool" "$tool" "/usr/lib/llvm-${LLVM_VERSION}/bin/$tool" 100; \
       done \
    && clang --version \
    && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -fsSL https://sh.rustup.rs \
      | sh -s -- -y --profile minimal --default-toolchain stable \
    && rustc --version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# An ARG, so that it bounds the memory this build uses without reaching the audit environment.
ARG CARGO_BUILD_JOBS=8

# Every crate, so cargo works offline during the audit.
RUN cargo fetch

# The release loader as shipped (embeds xdp/minecraft_filter.o, built by build.rs), plus a debug build and the test
# binaries. A step that fails fails the build, and primary_contact gets the log.
RUN cargo build --release \
    && cargo build \
    && cargo test --no-run

# Run the tests so the image is known to work, but do not let a failing test abort the build.
RUN cargo test || echo "WARNING: cargo test reported failures"
