# taOS backend (the FastAPI controller in tinyagentos/), installed the way CI installs it (.github/workflows/ci.yml):
# uv provisions Python, `uv sync --frozen` installs exactly what uv.lock records, including the dev group (pytest,
# pytest-asyncio, pytest-timeout, pytest-xdist, respx). Node 22 is present because some backend tests execute
# desktop JavaScript under node and fail, rather than skip, without it. The desktop SPA is not built: tests/conftest.py
# stubs the bundle, so the backend suite does not need it.
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git curl build-essential pkg-config sqlite3 libsqlcipher-dev \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.8.17 /uv /uvx /usr/local/bin/
ENV UV_PYTHON_INSTALL_DIR=/opt/uv-python \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1
RUN uv python install 3.12

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Exact versions from uv.lock (fails if the lock is stale), project installed editable into /src/.venv.
RUN uv sync --frozen --python 3.12

# The scan runs offline: put the venv first on PATH so `python -m pytest` works without uv, and stop uv from trying to
# resolve or download anything if someone does call `uv run`.
ENV PATH=/src/.venv/bin:$PATH \
    VIRTUAL_ENV=/src/.venv \
    UV_OFFLINE=1 \
    UV_NO_SYNC=1 \
    TAOS_DATA_DIR=/tmp/taos-data

# Hard check, same as CI's "Verify app starts": the app and every route module import.
RUN python -c "from tinyagentos.app import create_app; print('OK')" \
    && python -c "import pkgutil, importlib, tinyagentos.routes as r; mods=[importlib.import_module(n) for _, n, _ in pkgutil.walk_packages(r.__path__, 'tinyagentos.routes.')]; print('route modules:', len(mods))"

# Cheap security-relevant tests so you know the image works. A failure here does not abort the build.
# The full suite (about 10k tests) is: python -m pytest tests/ --ignore=tests/e2e -n auto
RUN (python -m pytest -q --tb=short -p no:cacheprovider \
       tests/test_auth_middleware.py tests/test_csrf.py tests/test_agent_token_auth.py \
       tests/test_security_headers.py tests/test_upload_body_limits.py \
     || echo "WARNING: security test subset reported failures")
