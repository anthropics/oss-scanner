FROM python:3.12-bookworm

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Include optional first-party integrations for analysis. The test suite uses
# synthetic data and mocked backends; no services or credentials are started.
COPY . /src
WORKDIR /src
RUN python -m pip install -e ".[dev,all,ai,indexer]" build hatchling

# Positive webhook tests resolve example.com. Supply a deterministic public-IP
# DNS answer only in this test process; normal application/audit DNS is unchanged.
RUN mkdir -p /opt/oss-scanner \
    && printf '%s\n' \
       'import socket' \
       'import sys' \
       'import pytest' \
       '' \
       'real_getaddrinfo = socket.getaddrinfo' \
       'def fixture_getaddrinfo(host, *args, **kwargs):' \
       '    if host == "example.com":' \
       '        host = "93.184.216.34"  # Synthetic DNS fixture; no connection.' \
       '    return real_getaddrinfo(host, *args, **kwargs)' \
       'socket.getaddrinfo = fixture_getaddrinfo' \
       'raise SystemExit(pytest.main(sys.argv[1:]))' \
       > /opt/oss-scanner/run-tests.py

RUN python -m build --wheel --no-isolation \
    && python /opt/oss-scanner/run-tests.py tests/test_alerts.py -q
