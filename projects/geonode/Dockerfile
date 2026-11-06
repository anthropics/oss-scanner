# syntax=docker/dockerfile:1
# Build GeoNode for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline, so everything the
# tests need is installed here. This follows the project's own Dockerfile (the geonode-base image, which
# carries the GDAL/GEOS/PROJ stack and the Python venv at /usr/src/venv) and the CI test stack
# (docker-compose.yml with .env_test), with PostGIS running inside the image and a stateless GeoServer stub
# in place of GeoServer. `geonode-services-start` starts both.
FROM geonode/geonode-base:latest-ubuntu-26.04

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# PostgreSQL and PostGIS from Ubuntu. The base image pins postgresql-client-common to PGDG, so
# postgresql-common has to come from PGDG too or the two conflict.
RUN printf 'Package: postgresql-common\nPin: release o=apt.postgresql.org\nPin-Priority: 500\n' \
        > /etc/apt/preferences.d/pgdg-common \
    && apt-get update -y \
    && apt-get install -y --no-install-recommends \
        curl wget unzip gnupg2 locales netcat-openbsd \
        postgresql-18 postgresql-18-postgis-3 \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir -U pip setuptools wheel

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

# GeoNode (editable) and its dev extras (pytest, coverage, flake8, black). The pycsw and MapStore client
# dependencies are fetched from GitHub, so this needs the network.
RUN pip install --no-cache-dir -e ".[dev]"

# The CI test environment (.env_test), with every service on localhost. Some values relax production
# defaults (API_LOCKDOWN, SAFE_URL_CHECK_ENABLED, CORS_ALLOW_ALL_ORIGINS); threat_model.md says findings
# must not depend on them.
ENV DJANGO_SETTINGS_MODULE=geonode.settings \
    DATABASE_URL=postgis://geonode:geonode@localhost:5432/geonode \
    GEODATABASE_URL=postgis://geonode_data:geonode_data@localhost:5432/geonode_data \
    DEFAULT_BACKEND_DATASTORE=datastore \
    ASYNC_SIGNALS=False \
    HARVESTING_MONITOR_ENABLED=False \
    SITEURL=http://localhost:8000/ \
    ALLOWED_HOSTS="['localhost', '127.0.0.1']" \
    SAFE_URL_CHECK_ENABLED=False \
    TIME_ENABLED=True \
    MOSAIC_ENABLED=False \
    GEOSERVER_LOCATION=http://localhost:8080/geoserver/ \
    GEOSERVER_PUBLIC_LOCATION=http://localhost:8080/geoserver/ \
    GEOSERVER_WEB_UI_LOCATION=http://localhost:8080/geoserver/ \
    OGC_REQUEST_TIMEOUT=5 \
    OGC_REQUEST_MAX_RETRIES=0 \
    CATALOGUE_ENGINE=geonode.catalogue.backends.pycsw_local \
    CATALOGUE_URL=http://localhost:8000/catalogue/csw \
    X_FRAME_OPTIONS=SAMEORIGIN \
    DEFAULT_ANONYMOUS_PERMISSIONS=download \
    DEFAULT_REGISTERED_MEMBERS_PERMISSIONS=download \
    CORS_ALLOW_ALL_ORIGINS=True \
    ACCOUNT_OPEN_SIGNUP=True \
    ACCOUNT_CONFIRM_EMAIL_ON_GET=False \
    ACCOUNT_EMAIL_VERIFICATION=none \
    SOCIALACCOUNT_OIDC_PROVIDER_ENABLED=True \
    API_LOCKDOWN=False \
    DEBUG=False \
    STATIC_ROOT=/mnt/volumes/statics/static/ \
    MEDIA_ROOT=/mnt/volumes/statics/uploaded/ \
    CLIENT_RESULTS_LIMIT=5 \
    API_LIMIT_PER_PAGE=1000 \
    AVATAR_GRAVATAR_SSL=True \
    CREATE_LAYER=True \
    DEFAULT_MAX_PARALLEL_UPLOADS_PER_USER=100

# The two databases GeoNode uses (the catalogue and the vector datastore), owned by roles that are
# superusers like test.sh makes them, so the test runner can create test_geonode and test_geonode_data
# with the postgis extension.
RUN pg_ctlcluster 18 main start \
    && su postgres -c "psql -v ON_ERROR_STOP=1" <<'SQL' \
    && pg_ctlcluster 18 main stop
ALTER ROLE postgres PASSWORD 'postgres';
CREATE ROLE geonode LOGIN SUPERUSER PASSWORD 'geonode';
CREATE ROLE geonode_data LOGIN SUPERUSER PASSWORD 'geonode_data';
CREATE DATABASE geonode OWNER geonode;
CREATE DATABASE geonode_data OWNER geonode_data;
\c geonode
CREATE EXTENSION postgis;
\c geonode_data
CREATE EXTENSION postgis;
SQL

# GeoServer stand-in on localhost:8080. Without it most dataset, permission and importer code paths fail on
# their first REST call (workspace lookup, GeoFence sync). It keeps no state, so tests that read back what
# GeoServer stored (GeoFence rule counts, published layers, rendered thumbnails) still fail.
COPY --chmod=755 <<'EOF' /usr/local/bin/geoserver-stub
#!/usr/bin/env python
"""Minimal GeoServer stand-in: empty but well-formed answers to GeoNode's REST, GeoFence and OWS calls."""
import base64
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

PLURALS = {
    "workspaces": "workspace",
    "datastores": "dataStore",
    "coveragestores": "coverageStore",
    "featuretypes": "featureType",
    "coverages": "coverage",
    "layers": "layer",
    "styles": "style",
    "layergroups": "layerGroup",
    "namespaces": "namespace",
    "wmsstores": "wmsStore",
}
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)
XML, JSON = "application/xml", "application/json"


def respond(method, url):
    path = urlsplit(url).path
    query = {k.lower(): v[0] for k, v in parse_qs(urlsplit(url).query).items()}
    request = query.get("request", "").lower()
    if "/rest/geofence/" in path:
        if path.endswith("/count.json"):
            return 200, JSON, b'{"count": 0}'
        if method == "GET":
            return 200, JSON, b'{"count": 0, "rules": []}'
        return 200, JSON, b"{}"
    m = re.search(r"/rest/(.*?)(?:\.(xml|json))?$", path)
    if m:
        status = 201 if method == "POST" else 200
        if m.group(2) == "json":
            return status, JSON, b"{}"
        parts = m.group(1).split("/")
        if parts == ["workspaces"] or parts == ["workspaces", "default"]:
            ws = b"<workspace><name>geonode</name></workspace>"
            return status, XML, ws if parts[-1] == "default" else b"<workspaces>" + ws + b"</workspaces>"
        if parts[-1] in PLURALS:
            return status, XML, f"<{parts[-1]}/>".encode()
        if len(parts) >= 2 and parts[-2] in PLURALS:
            tag = PLURALS[parts[-2]]
            return status, XML, f"<{tag}><name>{parts[-1]}</name><enabled>true</enabled></{tag}>".encode()
        return status, XML, b"<root/>"
    if request == "getmap" or path.endswith(".png"):
        return 200, "image/png", PNG
    if request == "describefeaturetype":
        return 200, XML, b'<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"/>'
    return 200, XML, b"<ServiceExceptionReport/>"


class Handler(BaseHTTPRequestHandler):
    def handle_any(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length:
            self.rfile.read(length)
        status, ctype, body = respond(self.command, self.path)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = handle_any

    def log_message(self, fmt, *args):
        if "-v" in sys.argv:
            super().log_message(fmt, *args)


ThreadingHTTPServer(("127.0.0.1", 8080), Handler).serve_forever()
EOF

COPY --chmod=755 <<'EOF' /usr/local/bin/geonode-services-start
#!/bin/sh
set -e
pg_isready -q -h localhost || pg_ctlcluster 18 main start
nc -z localhost 8080 2>/dev/null || (nohup geoserver-stub > /var/log/geoserver-stub.log 2>&1 &)
timeout 60 sh -c "until pg_isready -q -h localhost && nc -z localhost 8080 2>/dev/null; do sleep 0.5; done"
EOF

RUN mkdir -p /mnt/volumes/statics/static /mnt/volumes/statics/uploaded

# Migrate both databases and load the admin user (admin/admin) and the initial data, as the entrypoint's
# `invoke migrations` and `invoke fixtures` do, so `manage.py runserver` works offline.
RUN geonode-services-start \
    && python manage.py migrate --noinput \
    && python manage.py migrate dynamic_models --noinput --database=datastore \
    && python manage.py loaddata sample_admin initial_data.json \
    && pg_ctlcluster 18 main stop
