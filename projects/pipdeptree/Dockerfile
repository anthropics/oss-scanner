FROM rust:1-bookworm AS rust
FROM python:3.15-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PATH=/opt/venv/bin:/usr/local/cargo/bin:$PATH

COPY --from=rust /usr/local/cargo /usr/local/cargo
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential graphviz pkg-config \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv /opt/venv

COPY . /src
WORKDIR /src

RUN pip install --upgrade pip \
    && pip install . --group test \
    && pip wheel --no-deps --wheel-dir /opt/wheels .

RUN python -m pytest tests -q
