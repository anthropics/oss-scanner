# Selora AI is a Home Assistant custom integration (custom_components/selora_ai) with a Lit panel
# (custom_components/selora_ai/frontend). There is nothing to compile: the image installs the pinned
# Home Assistant test stack the project's CI uses, and the frontend's dev dependencies, so the Python
# suite (pytest-homeassistant-custom-component) and the panel suite (vitest) both run offline.
FROM node:22-bookworm-slim AS node

FROM python:3.14-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# gcc/g++: pymicro-vad and pyspeex-noise (needed by HA's assist_pipeline) ship no wheel for 3.13+.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git gcc g++ python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The same test stack as the project's CI (.gitlab-ci.yml, `.ha-test-deps`). The PHCC cap pins the Home
# Assistant core version; scripts/core_test_requirements.py adds the core components' own requirements.
RUN pip install pytest pytest-asyncio pytest-timeout \
      "pytest-homeassistant-custom-component<0.13.368" "ruamel.yaml>=0.18" anthropic PyJWT "rapidfuzz>=3.0" \
    && pip install $(python scripts/core_test_requirements.py)

RUN cd custom_components/selora_ai/frontend && npm ci

# Run the suites so the image is known to work, without letting a failing test abort the build.
RUN (pytest tests/ -q -p no:cacheprovider || echo "WARNING: pytest reported failures") \
    && (cd custom_components/selora_ai/frontend && npm test || echo "WARNING: vitest reported failures")
