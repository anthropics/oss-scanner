FROM rust:bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    RUSTFLAGS="-C debuginfo=1"

# Install GUI build dependencies for eframe/egui on Linux, plus runtime utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      pkg-config \
      git \
      python3 \
      tmux \
      libx11-dev \
      libxcb1-dev \
      libxcursor-dev \
      libxrandr-dev \
      libxi-dev \
      libgl1-mesa-dev \
      libxkbcommon-dev \
      libgtk-3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Pre-fetch crates while network is active
RUN cargo fetch --locked

# Pre-build dependencies and test harnesses for offline scanning
RUN cargo test --locked --no-run

# Baseline test run (warning only if GUI-related display tests fail in headless container)
RUN cargo test --locked || echo "WARNING: baseline cargo test had non-zero exit in headless environment"
