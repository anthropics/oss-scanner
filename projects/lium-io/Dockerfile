# Builds Datura-ai/lium-io the way its CI does (.github/workflows/test.yml): Python 3.11, pdm, and one
# `pdm install` per package (validators, executor, miners, watchtower). The executor pins Python ==3.11.11.
# lium_protocol and packages/lium-core are pip packages, so they go into one shared venv.
FROM python:3.11.11-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PDM_CHECK_UPDATE=false \
    PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential openssh-client \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pdm

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Each package gets its own .venv from its own pdm.lock. The neurons install ../../datura from the checkout.
RUN for pkg in neurons/validators neurons/executor neurons/miners watchtower; do \
      (cd /src/$pkg && pdm install) || exit 1; \
    done
RUN python -m venv /opt/lium-libs \
    && /opt/lium-libs/bin/pip install --no-cache-dir pytest "pydantic==2.13.*" /src/lium_protocol /src/packages/lium-core

# Cheap unit tests, as CI runs them. A failure is printed and does not fail the build.
RUN cd /src/neurons/validators && env BITTENSOR_WALLET_NAME=test_wallet BITTENSOR_WALLET_HOTKEY_NAME=test_hotkey \
      SQLALCHEMY_DATABASE_URI=sqlite:///test.db ASYNC_SQLALCHEMY_DATABASE_URI=sqlite+aiosqlite:///test.db \
      ENABLE_TDX_ATTESTATION=True TDX_VERIFIER_URL=http://localhost:8000/verify \
      pdm run pytest tests/ -q --tb=short || echo "WARNING: validators tests reported failures"
RUN cd /src/neurons/executor && mkdir -p tmp && (pdm run pytest tests/ -q --tb=short || echo "WARNING: executor tests reported failures")
RUN cd /src/neurons/miners && (pdm run pytest tests/ -q --tb=short || echo "WARNING: miners tests reported failures")
RUN cd /src/watchtower && (pdm run pytest tests/ -q --tb=short || echo "WARNING: watchtower tests reported failures")
RUN cd /src/lium_protocol && (/opt/lium-libs/bin/python -m pytest tests -q --tb=short || echo "WARNING: lium_protocol tests reported failures")
RUN cd /src/packages/lium-core && (/opt/lium-libs/bin/python -m pytest tests -q --tb=short || echo "WARNING: lium-core tests reported failures")
