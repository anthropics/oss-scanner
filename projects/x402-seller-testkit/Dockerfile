FROM node:22-bookworm

# Fetch the declared package manager and all locked dependencies online.
# The scanner's offline phase uses the installed tools and deterministic mocks.
RUN npm install --global pnpm@10.32.1
COPY . /src
WORKDIR /src
RUN pnpm install --frozen-lockfile
RUN pnpm check && pnpm build
