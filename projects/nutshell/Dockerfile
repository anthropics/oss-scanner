FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONUNBUFFERED=1 \
    MINT_BACKEND_BOLT11_SAT=FakeWallet \
    MINT_BACKEND_BOLT11_USD=FakeWallet \
    WALLET_NAME=test_wallet \
    MINT_HOST=localhost \
    MINT_PORT=3337 \
    TOR=false

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential git pkg-config libffi-dev libpq-dev \
      autoconf automake libtool ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry==2.3.2

# Install the project and its test tools while Internet access is available.
COPY . /src
WORKDIR /src
RUN poetry install --with dev --no-interaction

# Run tests after the build with networking disabled:
# poetry run pytest tests -q --ignore=tests/fuzz --deselect=tests/mint/test_mint_operations.py::test_melt_preserves_change_signatures_order_integration
