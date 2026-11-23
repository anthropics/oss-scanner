FROM rust:1-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-dev python3-venv \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=C.UTF-8 \
    PATH="/opt/venv/bin:$PATH" \
    PYO3_PYTHON=/opt/venv/bin/python \
    RUSTFLAGS="-C force-frame-pointers=yes"

RUN /usr/bin/python3 -m venv /opt/venv \
    && python -m pip install --no-cache-dir \
      'maturin>=1.9.4,<2' 'pytest>=7' 'pytest-asyncio>=0.21,<2' \
      'pytest-benchmark>=3.4' 'typing-extensions>=4.2'

COPY . /src
WORKDIR /src

# UI-test snapshots depend on the Rust compiler version.
RUN UI_TEST=skip cargo test --locked \
      -p pyo3 -p pyo3-build-config -p pyo3-ffi -p pyo3-macros -p pyo3-macros-backend \
      --features pyo3/full

RUN maturin build --locked --manifest-path pytests/Cargo.toml --interpreter "$PYO3_PYTHON" \
      --features experimental-async,experimental-inspect --out /tmp/wheels \
    && python -m pip install --no-deps /tmp/wheels/*.whl \
    && rm -rf /tmp/wheels \
    && python -m pytest pytests/tests
