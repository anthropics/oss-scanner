FROM hexpm/elixir:1.19.5-erlang-28.0.4-debian-bookworm-20260824-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential clang git curl ca-certificates python3 pkg-config libsqlite3-dev libvips-dev \
      zip unzip rsync \
    && rm -rf /var/lib/apt/lists/*
RUN mix local.hex --force && mix local.rebar --force

# Native adoption tests use the same mob_new templates as the project's CI.
RUN git clone https://github.com/GenericJam/mob_new.git /opt/mob_new
ENV MOB_NEW_DIR=/opt/mob_new

COPY . /src
WORKDIR /src
RUN MIX_ENV=dev mix deps.get \
    && MIX_ENV=test mix deps.get \
    && MIX_ENV=dev mix compile \
    && MIX_ENV=test mix compile
ENV HEX_OFFLINE=1
