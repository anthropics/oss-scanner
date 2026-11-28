# MCP reference servers: four TypeScript servers (npm workspaces) and three Python servers (one uv project each),
# installed, built and tested the way CI (.github/workflows/typescript.yml and python.yml) does. trixie, because the
# git server's merge tests expect a newer Git than bookworm has.
FROM node:24-trixie

COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /uvx /usr/local/bin/

ENV CI=true \
    UV_LINK_MODE=copy \
    UV_PYTHON_PREFERENCE=only-managed \
    UV_PYTHON_INSTALL_DIR=/opt/uv-python

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# npm ci also builds each TypeScript server, through its "prepare" script.
RUN npm ci && npm run build

# Each Python server pins its interpreter in .python-version; uv fetches it here.
RUN for server in fetch git time; do (cd src/$server && uv sync --frozen --all-extras --dev) || exit 1; done

# The fetch server's HTML simplifier (readabilipy) installs its JavaScript dependencies on first use: do it now.
RUN cd "$(src/fetch/.venv/bin/python -c 'import os, readabilipy; print(os.path.dirname(readabilipy.__file__))')/javascript" && npm install

# There is no network when the scanner runs, so uv and npm must use what is installed above.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    UV_PYTHON_DOWNLOADS=never \
    npm_config_offline=true

# A failing test must not abort the image build.
RUN timeout 300 npm test || echo "WARNING: npm test reported failures"
RUN for server in fetch git time; do (cd src/$server && timeout 300 uv run pytest -q) || echo "WARNING: pytest reported failures in $server"; done
