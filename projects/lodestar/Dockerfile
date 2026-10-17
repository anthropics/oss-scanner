FROM node:24.13.0-bookworm-slim

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true \
    NODE_OPTIONS=--max-old-space-size=6144

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git g++ make python3 python3-setuptools curl xz-utils \
    && rm -rf /var/lib/apt/lists/*

ARG TARGETARCH
RUN case "${TARGETARCH}" in \
      amd64) ZIG_ARCH=x86_64; ZIG_SHA256=70e49664a74374b48b51e6f3fdfbf437f6395d42509050588bd49abe52ba3d00 ;; \
      arm64) ZIG_ARCH=aarch64; ZIG_SHA256=ea4b09bfb22ec6f6c6ceac57ab63efb6b46e17ab08d21f69f3a48b38e1534f17 ;; \
      *) echo "Unsupported architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
    && curl -fsSL "https://ziglang.org/download/0.16.0/zig-${ZIG_ARCH}-linux-0.16.0.tar.xz" -o /tmp/zig.tar.xz \
    && echo "${ZIG_SHA256}  /tmp/zig.tar.xz" | sha256sum -c - \
    && tar -xJf /tmp/zig.tar.xz -C /opt \
    && ln -s "/opt/zig-${ZIG_ARCH}-linux-0.16.0/zig" /usr/local/bin/zig \
    && rm /tmp/zig.tar.xz

COPY . /src
WORKDIR /src

RUN corepack enable && corepack prepare --activate \
    && pnpm install --frozen-lockfile \
    && pnpm build

RUN pnpm download-spec-tests

CMD ["bash"]
