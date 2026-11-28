# Build Backend.AI for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline, so everything the
# tests need is installed here. The project pins CPython 3.13.7 (pants.toml interpreter_constraints).
FROM python:3.13.7-bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Build tools for the two sdist-only dependencies, and git-lfs for the binaries injected into containers.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git git-lfs jq \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# The runner/agent binaries (su-exec, jail, libbaihook, dropbear, ...) are Git LFS objects.
RUN (git lfs install --local --force && git lfs pull) \
    || echo "WARNING: git lfs pull failed; runner binaries stay pointers"

# Install the python-default resolve exactly as Pants pins it. python.lock is a uv lockfile whose root is a
# virtual project named "pants-lockfile-for-python-default" built from requirements.txt, so recreate that
# project next to a copy of the lock and sync it into /src/.venv. This is the environment `pants export`
# produces for development (./py uses it).
RUN mkdir -p /opt/bai-resolve \
    && cp python.lock /opt/bai-resolve/uv.lock \
    && python3 - <<'PY'
import json, pathlib
reqs = []
for line in pathlib.Path("/src/requirements.txt").read_text().splitlines():
    line = line.split("#", 1)[0].strip()
    if line and not line.startswith("-"):
        reqs.append(line)
deps = ",\n".join("    " + json.dumps(r) for r in reqs)
pathlib.Path("/opt/bai-resolve/pyproject.toml").write_text(
    '[project]\nname = "pants-lockfile-for-python-default"\nversion = "0.0.0"\n'
    f'requires-python = "==3.13.7"\ndependencies = [\n{deps}\n]\n'
)
PY
RUN UV_PROJECT_ENVIRONMENT=/src/.venv uv sync --frozen --project /opt/bai-resolve

# No network after this point. Tests import from src/ (as ./py does) and some fixtures read BACKEND_BUILD_ROOT.
ENV VIRTUAL_ENV=/src/.venv \
    PATH=/src/.venv/bin:$PATH \
    PYTHONPATH=/src/src \
    BACKEND_BUILD_ROOT=/src \
    UV_OFFLINE=1

# Run a fast slice of unit tests that need no Docker, PostgreSQL, Redis or etcd, so the image is known to
# work; a failing test must not abort the build. Many other unit tests start those services with
# testcontainers and cannot run in the scanner.
RUN python -m pytest -q -p no:cacheprovider \
      tests/unit/common/test_validators.py tests/unit/common/test_types.py tests/unit/common/jwt \
      tests/unit/kernel tests/unit/webserver tests/unit/storage_proxy \
      tests/unit/client --ignore=tests/unit/client/integration \
    || echo "WARNING: pytest reported failures"
