# Terraform Module Releaser: a GitHub Action written in TypeScript (strict, ESM) that runs on Node 24.
# The build context is the repository checkout. Everything the tests need is fetched here, because the scan runs
# offline.
FROM node:24-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CI=true
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git sudo \
    && rm -rf /var/lib/apt/lists/*

# terraform-docs is a runtime dependency: the action downloads it on the runner to generate wiki pages. Install the
# default version from action.yml (`terraform-docs-version`) so the real binary is available offline.
ARG TERRAFORM_DOCS_VERSION=v0.21.0
RUN arch="$(dpkg --print-architecture)" \
    && curl -sSLfo /tmp/terraform-docs.tar.gz \
      "https://terraform-docs.io/dl/${TERRAFORM_DOCS_VERSION}/terraform-docs-${TERRAFORM_DOCS_VERSION}-linux-${arch}.tar.gz" \
    && tar -xzf /tmp/terraform-docs.tar.gz -C /usr/local/bin terraform-docs \
    && chmod +x /usr/local/bin/terraform-docs \
    && rm /tmp/terraform-docs.tar.gz \
    && terraform-docs --version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Several code paths shell out to git and need an identity and a trusted directory.
RUN git config --global user.name "oss-scanner" \
    && git config --global user.email "oss-scanner@localhost" \
    && git config --global --add safe.directory '*'

# Install the locked dependencies, type-check, and bundle with ncc exactly as the release pipeline does.
RUN npm ci --no-fund --no-audit \
    && npm run lint:types \
    && npm run package

# Run the tests. The suites that call the real GitHub API need GITHUB_TOKEN and fail in setup without it; that is
# expected here. Failing tests do not abort the build.
RUN npm test || echo "WARNING: vitest reported failures"
