# PegaProx is a Python web application (Flask on gevent) that manages Proxmox VE, Proxmox
# Backup Server and XCP-ng clusters. Nothing is compiled: the build installs the runtime and
# test dependencies the way the project's CI does.
FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1

# gcc and the headers build the few wheels some platforms lack; openssh-client and sshpass
# are what PegaProx calls to reach cluster nodes
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git gcc libffi-dev libssl-dev openssh-client sshpass procps \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt -r requirements-dev.txt

# The full suite (about 13,000 tests) takes close to an hour on one core, so the build runs
# a security-focused sample. Every test stays in /src/tests: python -m pytest -q tests/<file>.py
RUN python -m pytest -q -p no:cacheprovider \
      tests/test_csrf_origin.py \
      tests/test_authz_isolation.py \
      tests/test_authz_fails_closed_when_it_cannot_tell.py \
      tests/test_console_endpoint_and_auth.py \
      tests/test_integration_ssrf_route.py \
    || echo "WARNING: pytest reported failures"

CMD ["bash"]
