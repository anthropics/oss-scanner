# OSS Scanner 构建环境：构建期联网装依赖，扫描期离线运行
ARG NODE_IMAGE=node:22-bookworm
FROM ${NODE_IMAGE}

ENV PNPM_HOME=/pnpm \
    PATH=/pnpm:$PATH \
    CI=true

RUN corepack enable \
 && corepack prepare pnpm@12.14.0 --activate

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      git ca-certificates python3 make g++ \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /src
COPY . .

# 仓库把内核放在 vendor/ds-core 子模块；扫描器克隆时可能不带子模块
RUN if [ -d .git ]; then \
      git submodule update --init --recursive; \
    else \
      rm -rf vendor/ds-core; \
      git clone --depth 1 https://github.com/Blue-Frontier/ds-core.git vendor/ds-core; \
    fi

# 只装内核与代理所需的依赖，避免 Electron GUI 的下载与打包
RUN pnpm install --frozen-lockfile \
      --filter @blue-frontier/dev-sidecar... \
      --filter @blue-frontier/mitmproxy...

# 扫描器要求离线环境可构建；内核单测不依赖网络，先跑一遍确认依赖与原生模块可用。
# mitmproxy 的测试会访问真实 DNS/ECH 端点，离线环境不执行。
RUN pnpm --filter @blue-frontier/dev-sidecar test