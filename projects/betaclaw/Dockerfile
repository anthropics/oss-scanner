FROM node:22-bookworm-slim

ENV HUSKY=0
WORKDIR /src

RUN corepack enable && corepack prepare pnpm@10.30.1 --activate

COPY package.json pnpm-lock.yaml ./
COPY scripts/avatar/sync-headaudio-assets.mjs ./scripts/avatar/sync-headaudio-assets.mjs
RUN pnpm config set node-linker hoisted && pnpm install --frozen-lockfile

COPY . .
RUN NEXTAUTH_SECRET=build-only-not-for-runtime pnpm run build
