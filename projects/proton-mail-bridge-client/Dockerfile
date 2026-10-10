FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates build-essential python3 git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Native module (better-sqlite3) and TypeScript build; both need the network, which is only available here.
RUN npm ci && npm run build

# Cheap, offline tests (they use stubbed IMAP/SMTP, no Proton Bridge needed). A failing test does not abort the build.
RUN (npm test || echo "WARNING: tests reported failures")
