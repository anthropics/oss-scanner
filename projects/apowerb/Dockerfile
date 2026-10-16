# Builds apowerb from the checkout the way its unit-test workflow (.github/workflows/tests.yml) does:
# Python 3.13, uv, an editable install plus the test tools, then the unit suite without a server or Postgres.
FROM python:3.13-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    DB_SCHEMA=""

# Build headers for the native dependencies (psycopg2, pyodbc), plus git for the scanner.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl git libpq-dev unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv==0.13.1

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# uv, not pip: apowerb's dependency set has an fsspec conflict (pins vs s3fs) that only uv resolves.
RUN uv venv /opt/venv --python 3.13 \
    && uv pip install -e . pytest pytest-asyncio anyio httpx greenlet

# The token-encryption code needs a real 32-byte urlsafe-base64 key; a placeholder string fails every
# encryption test. This one is generated per image and protects nothing.
RUN python -c "import base64, os; print('ENCRYPT_KEY=' + base64.urlsafe_b64encode(os.urandom(32)).decode())" > /etc/apowerb-test.env

# The same selection as CI: integration tests need a live server, tests/unit_scei and test_scei_* import a
# private overlay that is not in this repository, and the listed files are known pre-existing failures.
# A failing test does not fail the image.
RUN set -a && . /etc/apowerb-test.env && set +a \
    && (pytest -q -m "not integration" -p no:cacheprovider \
          --ignore=tests/unit_scei \
          --ignore-glob="tests/test_scei*" \
          --ignore=tests/test_integration_auth.py \
          --ignore=tests/test_integration_token_encryption.py \
          --ignore=tests/test_template_drift.py \
          --ignore=tests/test_callback_wiring.py \
          --ignore=tests/test_webhook_retrigger.py \
          --ignore=tests/test_tool_context_canonical.py \
          --ignore=tests/test_superagent_template_visibility.py \
          --ignore=tests/test_scheduled_emailing.py \
          --ignore=tests/test_callbacks.py \
          --ignore=tests/test_webhook_gmail_signature.py \
          --ignore=tests/test_microsoft_token_refresh.py \
          --ignore=tests/test_audio_streaming.py \
          --ignore=tests/test_pdf_first_page.py \
          --ignore=tests/test_chat_action_tools.py \
        || echo "WARNING: pytest reported failures")
