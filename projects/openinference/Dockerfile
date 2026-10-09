# Builds OpenInference (Python, JavaScript, Java and Go instrumentation) for the OSS Scanner.
# Network access is available here and removed afterwards, so every dependency the tests need is installed now.
FROM node:22-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    UV_PYTHON=3.12 \
    UV_HTTP_TIMEOUT=300 \
    UV_HTTP_RETRIES=5 \
    PNPM_HOME=/pnpm \
    GOTOOLCHAIN=local \
    PATH=/usr/local/go/bin:/root/go/bin:/pnpm:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates build-essential git curl openjdk-17-jdk-headless \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /uvx /usr/local/bin/
# Go, at the version go/go.work asks for.
RUN ARCH="$(dpkg --print-architecture)" \
    && curl -fsSL "https://go.dev/dl/go1.25.0.linux-${ARCH}.tar.gz" | tar -C /usr/local -xz

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Python: one virtualenv per package, each with the shared semantic conventions and core instrumentation installed in
# editable mode plus that package's `test` extra and test-requirements.txt (what tox installs). Run a package's tests with e.g.
#   cd python/instrumentation/openinference-instrumentation-openai && .venv/bin/pytest tests
# A package whose dependencies do not resolve is reported and skipped rather than failing the build.
RUN uv python install 3.12 && cd /src/python \
    && ls -d openinference-semantic-conventions openinference-instrumentation instrumentation/*/ | sed 's:/$::' \
     | xargs -P "$(nproc)" -I{} sh -c '\
         d="$1"; [ -f "$d/pyproject.toml" ] || exit 0; \
         x=""; grep -q "^test = \[" "$d/pyproject.toml" && x="[test]"; \
         { uv venv -q "$d/.venv" \
           && uv pip install -q --python "$d/.venv" -r dev-requirements.txt \
                -e openinference-semantic-conventions -e openinference-instrumentation -e "$d$x" \
           && { [ ! -f "$d/test-requirements.txt" ] || uv pip install -q --python "$d/.venv" -r "$d/test-requirements.txt"; }; \
         } || echo "WARNING: could not install $d"' _ {} \
    && uv cache clean -q

# JavaScript: install the pnpm workspace and build every package.
RUN npm i -g corepack && corepack enable \
    && cd /src/js && corepack install \
    && pnpm install --frozen-lockfile \
    && pnpm -r run prebuild && pnpm -r run build

# Java: compile main and test sources, then run the tests once so their runtime dependencies are cached too.
RUN cd /src/java && ./gradlew --no-daemon --parallel testClasses \
    && (timeout 600 ./gradlew --no-daemon --parallel test || echo "WARNING: java tests failed")

# Go: download every workspace module's dependencies and compile its code and tests.
RUN cd /src/go && for m in $(go list -m -f '{{.Dir}}'); do \
      (cd "$m" && go mod download && go build ./... && go test -count=1 -run '^$' ./...) \
      || echo "WARNING: go build failed in $m"; \
    done

# Smoke-test the image; failing tests do not abort the build.
RUN for d in openinference-instrumentation instrumentation/openinference-instrumentation-openai; do \
      (cd "/src/python/$d" && timeout 600 .venv/bin/pytest -q -p no:randomly tests) || echo "WARNING: python tests failed in $d"; \
    done \
    && cd /src/js && (pnpm --filter @arizeai/openinference-core test || echo "WARNING: js tests failed")
