FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    HUSKY=0 \
    CI=true
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Plain JavaScript, no build step. uWebSockets.js ships prebuilt binaries and is fetched from GitHub here.
RUN npm ci

# Comparison tests (each runs the same app on Express and on Fulmine) and unit tests.
RUN npm test || echo "WARNING: tests reported failures"
RUN npm run test:unit || echo "WARNING: unit tests reported failures"

# Express's own test suite, run against Fulmine. It clones expressjs/express into
# node_modules/express-suite-clone, so it has to run here, while the network is up.
RUN npm run test:express || echo "WARNING: Express suite reported failures"
