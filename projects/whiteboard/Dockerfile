FROM node:24.18.0-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang \
    CXX=clang++
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates clang cmake curl git pkg-config python3 \
      libx11-dev libxkbfile-dev libkrb5-dev libsecret-1-dev \
      libgtk-3-0t64 libnss3 libasound2t64 libgbm1 libnotify4 \
      xvfb dbus-x11 unzip zip zstd \
    && rm -rf /var/lib/apt/lists/*
RUN npm install --global pnpm@11.1.2

COPY . /src
WORKDIR /src
RUN pnpm install --frozen-lockfile
RUN REVIEW_DESKTOP_CI_FAST=1 pnpm desktop:build
RUN pnpm exec playwright install --with-deps chromium

CMD ["bash"]
