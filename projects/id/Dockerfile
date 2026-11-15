FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git python3 python3-pip python3-venv \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

ENV PATH="/src/env/bin:$PATH"
RUN make dev \
    && (make test || echo "WARNING: make test reported failures")
