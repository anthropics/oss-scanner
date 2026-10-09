FROM python:3.12-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Include optional first-party integrations for analysis. The test suite uses
# synthetic data and mocked backends; no services or credentials are started.
COPY . /src
WORKDIR /src
RUN python -m pip install -e ".[dev,all,ai,indexer]" build hatchling
RUN python -m build --wheel --no-isolation \
    && python -m pytest tests/ -q \
       --ignore=tests/test_e2e.py --ignore=tests/locustfile.py
