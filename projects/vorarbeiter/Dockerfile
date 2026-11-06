FROM debian:trixie

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git jq procps sudo \
        build-essential pkg-config \
        python3 python3-dev python3-venv python-is-python3 \
        libcairo2 libcairo2-dev libgirepository-2.0-0 libgirepository-2.0-dev \
        gir1.2-json-1.0 \
        postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY . /src
WORKDIR /src

RUN uv sync --frozen --all-groups
ENV PATH="/src/.venv/bin:${PATH}"

RUN DATABASE_URL="sqlite+aiosqlite:///:memory:" \
    uv run pytest -v -n 4 || echo "WARNING: tests reported failures"

CMD ["bash"]
