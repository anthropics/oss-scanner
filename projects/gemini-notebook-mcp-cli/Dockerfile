FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash build-essential ca-certificates chromium curl git \
    && rm -rf /var/lib/apt/lists/*
RUN python -m pip install --no-cache-dir uv==0.11.19

# Scanner contract: the complete checkout and editable installation live at /src.
COPY . /src
WORKDIR /src
RUN uv sync --locked --dev && uv build

# Dependencies and build tooling are fetched above; audit commands work offline.
ENV PATH="/src/.venv/bin:${PATH}" \
    UV_OFFLINE=true
CMD ["bash"]
