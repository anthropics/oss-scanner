FROM golang:1.27.2-bookworm AS go-toolchain
FROM node:24.21.0-bookworm

COPY --from=go-toolchain /usr/local/go /usr/local/go
ENV PATH="/usr/local/go/bin:${PATH}" \
    GOTOOLCHAIN=local \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright \
    pnpm_config_verify_deps_before_run=false

RUN npm install --global pnpm@12.5.1

# Keep the complete workspace and dependency caches for offline checks and patches.
COPY . /src
WORKDIR /src
RUN go mod download \
    && make install \
    && pnpm --dir web exec playwright install --with-deps chromium \
    && make build

CMD ["bash"]
