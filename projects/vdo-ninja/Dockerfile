FROM node:22-bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive \
    UV_THREADPOOL_SIZE=2 \
    NODE_PATH=/opt/oss-scanner-tools/node_modules
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 chromium xvfb xauth fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
RUN npm install --prefix /opt/oss-scanner-tools --no-audit --no-fund playwright-core@1.64.1
COPY . /src
WORKDIR /src
# The browser application is served directly; there is no frontend build step.
RUN test -s index.html && test -s main.js && test -s webrtc.js \
    && chromium --version
