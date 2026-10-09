FROM hexpm/elixir:1.19.5-erlang-28.0.4-debian-bookworm-20260824-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential clang git curl ca-certificates python3 pkg-config libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*
RUN mix local.hex --force && mix local.rebar --force \
    && mix archive.install hex phx_new --force

# The generator's --local tests resolve these sibling sources, as in CI.
RUN git clone https://github.com/GenericJam/mob.git /opt/mob \
    && git clone https://github.com/GenericJam/mob_dev.git /opt/mob_dev
ENV MOB_DIR=/opt/mob MOB_DEV_DIR=/opt/mob_dev

COPY . /src
WORKDIR /src
RUN MIX_ENV=dev mix deps.get \
    && MIX_ENV=test mix deps.get \
    && MIX_ENV=dev mix compile \
    && MIX_ENV=test mix compile \
    && MIX_ENV=test mix test --exclude requires_android_ndk

# Integration tests above populate Hex package archives and compile generated
# local projects while networking is available. The scanner can repeat them
# offline from the retained Hex cache.
ENV HEX_OFFLINE=1
