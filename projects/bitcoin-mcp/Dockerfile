FROM python:3.12-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# The scanner supplies this repository as the build context. All dependencies
# are installed online here; tests use mocks and also run without a network.
COPY . /src
WORKDIR /src
RUN python -m pip install -e ".[dev,l402]" build hatchling
RUN python -m build --wheel --no-isolation \
    && python -m pytest tests/ -q
