# Scanner contract: the Keystone checkout is the build context and ends up at /src.
# Network is available only while this image builds. tox -e py3 and a SQLite
# API process must run afterwards with no network.
FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/src/.tox/py3/bin:/opt/venv/bin:$PATH \
    TOX_CONSTRAINTS_FILE=/opt/upper-constraints.txt

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git python3 python3-venv python3-dev \
        build-essential pkg-config \
        libffi-dev libssl-dev libldap2-dev libsasl2-dev \
        libsqlite3-dev libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv \
    && pip install tox

COPY . /src
WORKDIR /src

# Upper constraints pin the released package, which is not this checkout.
# Drop that one line and let tox install the tree the way the project does.
RUN git config --global --add safe.directory /src \
    && if ! git describe --tags >/dev/null 2>&1; then export PBR_VERSION=0.0.0; fi \
    && python -c "import urllib.request; t=urllib.request.urlopen('https://releases.openstack.org/constraints/upper/master').read().decode(); open('/opt/upper-constraints.txt','w').write(''.join(l for l in t.splitlines(True) if not l.lower().startswith('keystone===')))" \
    && tox -e py3 --notest \
    && /src/.tox/py3/bin/pip install uwsgi \
    && python -c "import keystone, keystone.server.wsgi"

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

ENTRYPOINT []
CMD ["bash"]
