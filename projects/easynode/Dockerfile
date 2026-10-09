# Dedicated Anthropic OSS Scanner environment; not a production image.
# Build from the EasyNode repository root:
# docker build -f .oss-scanner/Dockerfile -t easynode-oss-scanner .
FROM node:22-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    NODE_ENV=development

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git openssh-client \
    python3 make g++ pkg-config iputils-ping \
    && rm -rf /var/lib/apt/lists/*

RUN corepack enable && corepack prepare yarn@1.22.22 --activate

WORKDIR /workspace/easynode
COPY . .

# Install both backend and frontend dependencies while Internet access is available.
# Keep dev dependencies for test reproduction and static analysis.
RUN yarn install --frozen-lockfile --non-interactive
RUN yarn workspace web run build

# The scanner must be able to inspect the full source tree, not only a runtime image
# Do not start a production-facing server or contact real infrastructure by default.
WORKDIR /workspace/easynode
CMD ["bash"]
