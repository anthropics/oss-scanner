FROM golang:1.27.2-bookworm AS go-toolchain
FROM node:24.19.0-bookworm

COPY --from=go-toolchain /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}" \
    GOTOOLCHAIN=local \
    CGO_ENABLED=0 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    pnpm_config_verify_deps_before_run=false

RUN npm install --global pnpm@11.24.0

# The scanner supplies a clean public checkout and requires sources at /src.
COPY . /src
WORKDIR /src
RUN pnpm --filter './packages/client...' --filter './packages/admin...' \
      install --frozen-lockfile \
    && pnpm -C packages/client exec playwright install --with-deps chromium
RUN pnpm -C packages/client build && pnpm -C packages/admin build
RUN cd server && go mod download && go build -o /usr/local/bin/ecoku-server .

CMD ["bash"]
