FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git vim neovim python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Fetch the exact Vader revision recorded by the project while online.
RUN git submodule update --init --recursive
RUN vim -Es -u test/vimrc '+Vader! test/winresizer.vader'
