FROM node:22-bookworm-slim AS node

FROM python:3.12-slim-bookworm
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && apt-get update \
    && apt-get install -y --no-install-recommends bash build-essential ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Keep CPU-only dependencies: the scanner has no GPU. PyTorch's version matches
# the project's current lockfile; other requirements come from pyproject.toml.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"
RUN python -m pip install --no-cache-dir 'torch==2.14.0+cpu' --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install --no-cache-dir -e '.[dev,pretrained,jev]'

# Keep Node, node_modules, all source and tests in the final image for offline use.
RUN npm --prefix dashboard ci \
    && npm --prefix dashboard run build

ENV OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    TOKENIZERS_PARALLELISM=false \
    HF_HUB_OFFLINE=1 \
    HF_DATASETS_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    ARTIFACTS_ROOT=/tmp/plastic-scanner-artifacts
RUN plastic --help
CMD ["bash"]
