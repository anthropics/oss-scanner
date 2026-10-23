FROM node:24.15.0-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        python3 \
        make \
        g++ \
    && rm -rf /var/lib/apt/lists/*

RUN corepack enable \
    && corepack prepare pnpm@10.34.5 --activate

# The scanner requires the checked-out repository at /src.
COPY . /src
WORKDIR /src

# Fetch all dependencies while network access is available.
RUN pnpm install --frozen-lockfile

# Build every workspace so generated artifacts are available offline.
RUN pnpm build

# Run the repository's deterministic checks. Tests are left installed and
# available to the offline scanner even if an environment-specific suite fails.
RUN pnpm typecheck \
    && pnpm lint \
    && pnpm check:i18n \
    && pnpm check:parity \
    && pnpm check:no-secrets \
    && (pnpm test || echo "WARNING: pnpm test reported failures")
