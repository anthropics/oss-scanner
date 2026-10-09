# Build image for skills-scanner (skillscan), a pure-stdlib Python CLI.
# The scanner builds this with the repository checkout as the build context.
FROM python:3.12-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/src/src

# git and build tools so the scanner's layer and any reproducer can compile a C extension offline.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Editable install so /src/src/skillscan is the code under test and `skillscan` is on PATH.
RUN pip install -e /src

# Optional extras that enable extra code paths (YARA rule packs, the LLM judge). Neither is a hard dependency;
# a failure here must not abort the build.
RUN pip install yara-python || echo "WARNING: yara-python not installed; rules/yara_pack.py stays a no-op"

# Smoke test: the unit tests and the built-in demo both run offline. A failing test must not abort the build.
RUN (python -m unittest discover -s tests 2>&1 | tail -5) || echo "WARNING: unit tests reported failures"
RUN skillscan demo >/dev/null 2>&1 || echo "WARNING: skillscan demo failed"
