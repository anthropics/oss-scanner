# Build Code Puppy for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline, so everything the
# tests and the CLI need is installed here: Python 3.13 (what CI uses), the locked runtime dependencies,
# every optional extra, the dev dependency group (pytest, pytest-asyncio, pexpect, ...), and the Chromium
# build Playwright drives for the browser tools.
FROM docker.io/library/python:3.13-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON_PREFERENCE=only-system \
    UV_PYTHON=/usr/local/bin/python3.13 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git procps \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "uv==0.13.5"

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# code-puppy itself (editable) plus every locked runtime dependency, all extras and the dev group,
# from the committed uv.lock into /src/.venv.
RUN uv sync --locked --all-extras --group dev

# The network is gone after this point, so `uv run` must use the environment built above as it is,
# never try to re-resolve or re-sync it.
ENV UV_FROZEN=1 \
    UV_NO_SYNC=1 \
    UV_OFFLINE=1 \
    VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH

# The browser tools download Chromium on first use, which cannot work offline. Fetch it (and its system
# libraries) now.
RUN python -m playwright install --with-deps chromium && rm -rf /var/lib/apt/lists/*

# `code-puppy-tests [pytest args]` runs the suite the way CI does (.github/workflows/ci.yml): fake provider
# keys, CI=1, CODE_PUPPY_TEST_FAST=1, no coverage. Nothing in the suite needs a real model or the network.
# As root, 3 tests that chmod a file read-only and expect a write error fail (root ignores file modes);
# they pass as a non-root user.
RUN printf '%s\n' \
      '#!/bin/bash' \
      'set -euo pipefail' \
      'cd /src' \
      'for key in OPENAI_API_KEY ANTHROPIC_API_KEY CEREBRAS_API_KEY CONTEXT7_API_KEY SYN_API_KEY LILAC_API_KEY; do' \
      '  export "$key=${!key:-fake-key-for-ci-testing}"' \
      'done' \
      'export CI=1 CODE_PUPPY_TEST_FAST=1' \
      'exec python -m pytest -p no:cacheprovider --no-cov "${@:-tests}"' \
      > /usr/local/bin/code-puppy-tests \
    && chmod +x /usr/local/bin/code-puppy-tests

# Smoke test: the package imports and the CLI starts. Then the quick, offline-safe test files; a failing
# test must not abort the build. The full suite: `code-puppy-tests`.
RUN python -c "import code_puppy, code_puppy.main, code_puppy.tools, code_puppy.mcp_, code_puppy.plugins" \
    && code-puppy --help >/dev/null
RUN code-puppy-tests -q tests/test_atomic_io.py tests/plugins/test_plugin_trust.py tests/mcp/test_project_config.py \
      tests/tools/test_command_runner_env.py tests/test_provider_credentials.py \
    || echo "WARNING: pytest reported failures"
