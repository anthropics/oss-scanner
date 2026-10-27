FROM docker.io/library/rust:1.99.1-bookworm

# Install OpenSSL & C build essentials (required for the openssl backend)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libssl-dev \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

# Vendor all dependencies (including optional ones for rustls and openssl).
# Passing --versioned-dirs ensures all dependencies in Cargo.lock are vendored.
RUN cargo vendor vendor > .cargo-vendor-config.toml && \
    mkdir -p .cargo && \
    cat .cargo-vendor-config.toml >> .cargo/config.toml && \
    rm .cargo-vendor-config.toml

# Explicitly lock network access for Cargo
# ENV CARGO_NET_OFFLINE=true

# Build & test with OpenSSL (default)
# RUN cargo test --release --all-targets

# Build & test with the pure-Rust stack (rustls)
# RUN cargo test --release --all-targets --no-default-features --features rustls

CMD ["/bin/bash"]
