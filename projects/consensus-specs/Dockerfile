FROM ghcr.io/astral-sh/uv:latest AS uv
FROM python:3.14-trixie

# Install uv
COPY --from=uv /uv /uvx /usr/local/bin/

# Copy the repository
COPY . /src
WORKDIR /src

# Install dependencies and generate the executable specs
RUN make build

# The scan runs without network access
ENV UV_OFFLINE=1

# Run some tests to make sure everything works
RUN make test fork=phase0 k=sanity
