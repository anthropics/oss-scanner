# Verification status and exact source revision are recorded in the enrollment PR.
# Scanner contract: the project checkout is the build context and lives at /src.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=1 \
    HUSKY=0 \
    ASTRO_TELEMETRY_DISABLED=1 \
    CHROME_PATH=/usr/bin/chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential chromium fonts-liberation fonts-noto-cjk ffmpeg \
    && rm -rf /var/lib/apt/lists/*
RUN corepack enable && corepack prepare pnpm@10.32.1 --activate
# Fail the image build if required offline tools or real CJK fonts are absent.
RUN node --version && corepack pnpm@10.32.1 --version \
    && chromium --version && ffprobe -version && ffmpeg -version
RUN fc-match -f '%{family}\\n' 'sans-serif:lang=zh-cn' | grep -F 'Noto Sans CJK'
COPY . /src
WORKDIR /src
RUN corepack pnpm@10.32.1 install --frozen-lockfile
RUN corepack pnpm@10.32.1 build:packages
RUN corepack pnpm@10.32.1 docs:build
# Build failures are fatal. Run the documented tests in the resulting image
# with Internet access disabled; do not treat image construction as a test pass.
