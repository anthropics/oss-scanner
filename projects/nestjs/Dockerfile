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

# Same steps as CI (.circleci/config.yml): install, then compile every package under packages/.
RUN npm ci --legacy-peer-deps
RUN npm run build

# Unit tests (vitest). Integration tests under integration/ need Redis, NATS, RabbitMQ, Kafka, MQTT etc.
# via docker-compose and are not run here.
RUN npm run test || echo "WARNING: unit tests reported failures"
