FROM ghcr.io/astral-sh/uv:latest AS uv
FROM python:3.14-trixie

# Install uv
COPY --from=uv /uv /uvx /usr/local/bin/

# Copy the repository
COPY . /src
WORKDIR /src

# Install the specification, the testing framework, and their dependencies
RUN uv sync --locked

# The scan runs without network access
ENV UV_OFFLINE=1

# Fill a small set of tests to make sure everything works
RUN uv run fill --fork Amsterdam --output /tmp/fixtures --clean tests/frontier/opcodes/test_dup.py
