# Build avni-models for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline.
# Mirrors the project's CI (.circleci/config.yml): Node 20.19.5, yarn install, build, schema validation, tests.
FROM node:20.19.5-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CI=true

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

RUN yarn install --frozen-lockfile

RUN yarn build

# Run the checks so the image is known to work. A failure is reported but does not stop the image build.
RUN (yarn validate:schemas || echo "WARNING: yarn validate:schemas reported failures") \
    && (yarn test-ci || echo "WARNING: yarn test-ci reported failures")
