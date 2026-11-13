FROM hexpm/elixir:1.19.5-erlang-28.0.4-debian-bookworm-20260824-slim

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential clang git curl ca-certificates python3 pkg-config libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*
RUN mix local.hex --force && mix local.rebar --force

COPY . /src
WORKDIR /src
RUN MIX_ENV=dev mix deps.get \
    && MIX_ENV=test mix deps.get \
    && MIX_ENV=dev mix compile \
    && MIX_ENV=test mix compile

# Docker's offline runtime has only a loopback interface, while this test
# verifies refusal on a non-loopback address. Exercise it during image build.
RUN MIX_ENV=test mix test test/mob/dist_test.exs

# These harnesses compile actual portable iOS headers. The stored-queue and
# Objective-C frame-registry harnesses require Apple frameworks/APIs.
RUN make -C test/native CC=clang dist_port_test dist_cookie_test init_args_test

# All Hex sources and registry records remain available for offline reproducers.
ENV HEX_OFFLINE=1
