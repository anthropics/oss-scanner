# OSS Scanner build for phasespace-labs/palinode. Kept beside project.yaml, so the scanner places it at
# .oss-scanner/Dockerfile in the checkout and deletes the repo's .dockerignore before building.
# Grounded in phasespace-labs/palinode@7d3acde51dd755a32f5c952d5ed1ccaf24cecb05:
#   pyproject.toml (requires-python >=3.11, extra "dev" = pytest, pytest-asyncio, pytest-timeout, ruff, bandit),
#   uv.lock (in sync with pyproject; mcp 2.0.0), .github/workflows/ci.yml (pip install -e ".[dev]";
#   pytest tests/ -v --tb=short --ignore=tests/integration), root Dockerfile (python:3.12-slim + git).
# Scanner contract (anthropics/oss-scanner templates/Dockerfile): build context = repo, COPY . /src, WORKDIR /src.
# Network exists ONLY during this build; scanning is fully offline.
# Limits: build 45 min on 16 CPU / 64 GB; scanning agent ~2 CPU / 8 GB.

# Python 3.12 on Debian bookworm. CI tests 3.11 and 3.12; the shipped Dockerfile uses 3.12.
# Full (non-slim) image so build tools exist for any sdist-only wheel and for the scanner's debugging.
# Its sqlite3 (3.40) allows enable_load_extension, which sqlite-vec needs; the sanity check below asserts it.
FROM python:3.12-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# git: every memory save is git-committed; git_tools.py shells out to git (blame/diff/history/rollback/push).
# poppler-utils: palinode/ingest/pipeline.py falls back to `pdftotext` when pymupdf is absent; installing it lets
# the scanner exercise that untrusted-document path offline.
# jq: the shipped Claude Code hooks (examples/hooks/*.sh) use it, and ~50 hook tests run them; without it they fail.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git jq poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# uv (any >=0.5; verified with 0.12.24), installed with pip, so the build uses the committed uv.lock
# (reproducible, offline-ready). CI itself uses pip; see the commented alternative below.
RUN pip install "uv>=0.5"

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src
# The scanner deletes the repo's .dockerignore before building (it would hide tests/ from the context). Restore it
# from git so /src matches the repository; tests/test_docker_compose.py asserts on it.
RUN git checkout -- .dockerignore

# Install the package (editable) plus the "dev" extra exactly as locked. Fails the build if uv.lock is out of
# sync with pyproject.toml (--frozen), which is what we want to hear about.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:${PATH}"
RUN uv sync --frozen --extra dev --python /usr/local/bin/python3.12
# Alternative that mirrors .github/workflows/ci.yml exactly (unlocked resolve):
#   RUN python -m venv /opt/venv && /opt/venv/bin/pip install -e ".[dev]"

# Sanity checks: package resolves to /src (same guard as CI) and SQLite can load extensions (sqlite-vec).
RUN python -c "import palinode, sys; assert palinode.__file__.startswith('/src/'), palinode.__file__; print(palinode.__file__)" \
 && python -c "import sqlite3, sqlite_vec; c=sqlite3.connect(':memory:'); c.enable_load_extension(True); sqlite_vec.load(c); print(c.execute('select vec_version()').fetchone())"

# Tests commit to temporary git repos and need an identity; set a throwaway one. No credentials.
RUN git config --global user.name "oss-scanner" \
 && git config --global user.email "oss-scanner@localhost" \
 && git config --global init.defaultBranch main \
 && git config --global --add safe.directory '*'

# No external services are fetched: ci.yml states all embeddings/LLM calls are mocked in the unit suite, and
# tests/conftest.py stubs the embedder. Ollama / bge-m3 (docker-compose.yml) are runtime-only and deliberately
# NOT pulled (~1.2 GB, not needed for tests). tests/live/ needs a running server and is excluded by pytest config.
# tests/integration/ only uses loopback (test_mcp_stdio.py spawns palinode-api on 127.0.0.1); verified to pass with
# `docker run --network none --cpus 2 --memory 8g`.

# Run the CI unit-test command so the build log shows the image works, without failing the build on test failures
# (the scanner template's advice: a failed build means no scan, and palinode's own CI already gates regressions).
# Two tests can fail in a container for environmental reasons, so they are deselected from the main
# run and recorded separately in known-failures.log. Any FAILED line in the main run is therefore unexpected.
#   test_alive_lock_is_skipped: the lock-reason PID regex needs 2+ digits; container PIDs can be single-digit.
#   test_unset_budget_renders_exactly_the_unbudgeted_digest: same-mtime ordering, fixed upstream after 7d3acde.
# Some tests log heavily (thousands of INFO lines), which overflows BuildKit's 2 MiB per-step log limit and clips the
# pytest summary. So the full output goes to /opt/test-baseline/ in the image (the pre-scan baseline) and only the
# failures and summary reach the build log.
RUN mkdir -p /opt/test-baseline \
 && (pytest tests/ -q --tb=short -rfE --ignore=tests/integration -p no:cacheprovider \
      --deselect tests/test_worktree_reconcile.py::test_alive_lock_is_skipped \
      --deselect tests/test_context_prime_budget.py::test_unset_budget_renders_exactly_the_unbudgeted_digest \
      > /opt/test-baseline/unit.log 2>&1 \
      || echo "WARNING: unexpected unit-test failures (see /opt/test-baseline/unit.log)") \
 && grep -E "^(FAILED|ERROR) |[0-9]+ (passed|failed|errors?)" /opt/test-baseline/unit.log | tail -n 40 \
 && (pytest tests/integration -q --tb=short -rfE -p no:cacheprovider > /opt/test-baseline/integration.log 2>&1 \
      || echo "WARNING: unexpected integration-test failures (see /opt/test-baseline/integration.log)") \
 && grep -E "^(FAILED|ERROR) |[0-9]+ (passed|failed|errors?)" /opt/test-baseline/integration.log | tail -n 40 \
 && (pytest -q --tb=short -rfE -p no:cacheprovider \
      tests/test_worktree_reconcile.py::test_alive_lock_is_skipped \
      tests/test_context_prime_budget.py::test_unset_budget_renders_exactly_the_unbudgeted_digest \
      > /opt/test-baseline/known-failures.log 2>&1 || true) \
 && echo "known container failures: $(tail -n 1 /opt/test-baseline/known-failures.log)" \
 && rm -rf /root/palinode /tmp/pytest-of-root
# (Some code writes ~/palinode at import time; drop it and pytest's temp dirs so the scan starts from a clean HOME.)

# The TypeScript delivery adapters (plugin/, plugins/) are outside the initial enrollment scope; see threat_model.md.
