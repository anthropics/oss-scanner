# Apache Magpie: a uv workspace of Python tools, plus TypeScript tests run by node.
# The build context is the repository root and runs with network; the audit of
# /src runs without it.

# pyproject.toml: requires-python = ">=3.11"
FROM python:3.11-slim-bookworm

# pyproject.toml: [tool.uv] required-version = ">=0.11.8"
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /uvx /usr/local/bin/

# .github/workflows/tests.yml: node-version "24", for the Pi extension's tests
# that the agent-isolation suite wraps (tools/agent-isolation/pi/).
COPY --from=node:24-bookworm-slim /usr/local/bin/node /usr/local/bin/node

# git: several suites build throwaway repositories. procps, jq: the shell tools
# and their fixtures (tools/spec-loop; tools/agent-isolation skips its settings
# work without jq).
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates procps jq \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# .github/workflows/tests.yml: `uv sync --frozen --group dev`, there per batch of
# members, here for all of them. --frozen: the lock is the input.
RUN uv sync --frozen --group dev --all-packages

# tools/skill-token-count fetches its vocabulary into its own cache on first use.
RUN uv run --frozen --project tools/skill-token-count skill-token-count --prepare-tokenizer \
    || echo "WARNING: tokenizer not cached; skill-token-count tests need network"

# Freeze for offline use.
ENV UV_FROZEN=1 UV_NO_SYNC=1 UV_OFFLINE=1 PATH="/src/.venv/bin:${PATH}"

# Smoke slice: the enforcement layer's offline suites.
RUN uv run --directory tools/vetted-ops pytest -q \
    && uv run --directory tools/agent-guard pytest -q \
    || echo "WARNING: tests reported failures"

# Further tests: `uv run --directory tools/<name> pytest -q` for one workspace member,
# or `tools/dev/run-workspace-check.sh pytest "pytest -n auto"` for all of them.
# Do not run pytest from /src: every member has its own `tests` package and
# plugins/*/tools/ holds generated copies, so a root run fails at collection.
