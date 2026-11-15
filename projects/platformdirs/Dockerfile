FROM python:3.15-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

COPY . /src
WORKDIR /src

RUN pip install --upgrade pip \
    && { git describe --tags >/dev/null 2>&1 || export SETUPTOOLS_SCM_PRETEND_VERSION=0.0.0; } \
    && pip install -e . --group test \
    && pip wheel --no-deps --wheel-dir /opt/wheels .

RUN python -m pytest tests -q
