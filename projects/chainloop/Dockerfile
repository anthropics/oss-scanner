# Scanner image for https://github.com/chainloop-dev/chainloop (main branch).
#
# Chainloop is a single Go module (github.com/chainloop-dev/chainloop) with three binaries: the
# control plane (app/controlplane), the artifact CAS (app/artifact-cas), and the CLI (app/cli). All
# generated code (protobuf/Connect, ent, wire) is checked in, so a plain checkout builds without any
# code-generation tools.
#
# This image builds everything and, so the audit can exercise the product the way it really runs,
# bakes a full offline stack into one container: Postgres, Vault, and Dex (OIDC), with the control
# plane's database migrations already applied. `chainloop-start` boots the whole stack on localhost
# with no network. See threat_model.md, next to this file, for how to drive it.
#
# The scanner builds this image with the network up and then audits with the network removed, so
# every dependency is fetched here. Integration tests use testcontainers (they need a Docker daemon,
# absent offline) and are gated by SKIP_INTEGRATION, so `go test ./...` runs the unit tests only.

# Go toolchain pinned to go.mod (go 1.27.3). GOTOOLCHAIN=local keeps go from fetching another
# toolchain once the network is gone; SKIP_INTEGRATION makes the testcontainers suites t.Skip().
FROM golang:1.27.3-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local \
    SKIP_INTEGRATION=true

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git build-essential procps curl postgresql postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Service binaries, copied from their official images (pure-Go, statically linked, so they run on the
# glibc base above). Pinned to the versions Chainloop's own devel/ compose stack uses.
#   vault — dev-mode credentials backend (KV v2 at secret/)
#   dex   — OIDC provider for login (in-memory storage, static users)
#   atlas — applies the control-plane database migrations
COPY --from=hashicorp/vault:1.12.3 /bin/vault /usr/local/bin/vault
COPY --from=ghcr.io/dexidp/dex:v2.43.1 /usr/local/bin/dex /usr/local/bin/dex
COPY --from=arigaio/atlas@sha256:3cd6883d5ec2703741f750fd5f9efed3a61f8e164b9dcea93ab7a7be429a1b5b /atlas /usr/local/bin/atlas

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every dependency; after this image is built there is no network.
RUN go mod download

# Build every package and all three binaries. Go keeps DWARF debug info and frame pointers by default,
# so reproducers stay legible. A step that fails fails the build, and primary_contact gets the log.
RUN go build ./... \
    && go build -o /usr/local/bin/chainloop-controlplane ./app/controlplane/cmd \
    && go build -o /usr/local/bin/chainloop-cas ./app/artifact-cas/cmd \
    && go build -o /usr/local/bin/chainloop ./app/cli

# Run the unit tests (integration tests skip via SKIP_INTEGRATION) so the caches are warm and the
# image is shown to work offline, without letting a failing test abort the build.
RUN timeout 1800 go test ./... || echo "WARNING: go test reported failures"

# --- Live offline stack -------------------------------------------------------------------------
# Postgres: trust auth on loopback, a `controlplane` database, and the control-plane migrations
# applied now so the schema is baked into the image's data directory.
RUN set -eux; \
    for conf in /etc/postgresql/*/main/pg_hba.conf; do \
      printf 'local all all trust\nhost all all 127.0.0.1/32 trust\nhost all all ::1/128 trust\n' > "$conf"; \
    done; \
    service postgresql start; \
    until pg_isready -q -h 127.0.0.1; do sleep 1; done; \
    su postgres -c "psql -v ON_ERROR_STOP=1 -c \"CREATE DATABASE controlplane\""; \
    atlas migrate apply \
      --dir "file:///src/app/controlplane/pkg/data/ent/migrate/migrations" \
      --url "postgres://postgres:@127.0.0.1:5432/controlplane?sslmode=disable"; \
    service postgresql stop

# chainloop-start boots Postgres, Vault, Dex, the control plane and the artifact CAS on loopback with
# no network. Logs go to /tmp/chainloop/*.log. It is safe to run again; `chainloop-stop` tears it down.
COPY --chmod=755 <<'EOF' /usr/local/bin/chainloop-start
#!/bin/bash
# Full offline Chainloop stack:
#   Postgres       127.0.0.1:5432  db controlplane, user postgres (trust auth)
#   Vault (dev)    127.0.0.1:8200  token notasecret, KV v2 at secret/
#   Dex (OIDC)     127.0.0.1:5556/dex  static login  john@chainloop.local / password
#   control plane  HTTP 127.0.0.1:8000, gRPC 127.0.0.1:9000  (GET /statusz)
#   artifact CAS   HTTP 127.0.0.1:8001, gRPC 127.0.0.1:9001  (GET /statusz)
set -e
mkdir -p /tmp/chainloop /tmp/chainloop-cas-staging

wait_for() { for _ in $(seq 1 "${3:-60}"); do curl -fsS "$2" >/dev/null 2>&1 && return 0; sleep 1; done; echo "timeout waiting for $1" >&2; return 1; }

service postgresql start >/dev/null 2>&1 || true
until pg_isready -q -h 127.0.0.1; do sleep 1; done

if ! curl -fsS http://127.0.0.1:8200/v1/sys/health >/dev/null 2>&1; then
  vault server -dev -dev-root-token-id=notasecret -dev-listen-address=0.0.0.0:8200 \
    >/tmp/chainloop/vault.log 2>&1 &
  wait_for vault http://127.0.0.1:8200/v1/sys/health 30
fi

if ! curl -fsS http://127.0.0.1:5556/dex/.well-known/openid-configuration >/dev/null 2>&1; then
  ( cd /src/devel/dex && exec dex serve config.dev.yaml ) >/tmp/chainloop/dex.log 2>&1 &
  wait_for dex http://127.0.0.1:5556/dex/.well-known/openid-configuration 30
fi

if ! curl -fsS http://127.0.0.1:8000/statusz >/dev/null 2>&1; then
  ( cd /src/app/controlplane && \
    CP_DB_HOST=127.0.0.1 CP_VAULT_ADDRESS=http://127.0.0.1:8200 CP_VAULT_TOKEN=notasecret \
    exec chainloop-controlplane --conf configs/config.devel.yaml ) >/tmp/chainloop/controlplane.log 2>&1 &
fi

if ! curl -fsS http://127.0.0.1:8001/statusz >/dev/null 2>&1; then
  ( cd /src/app/artifact-cas && \
    CAS_VAULT_ADDRESS=http://127.0.0.1:8200 CAS_VAULT_TOKEN=notasecret \
    exec chainloop-cas --conf configs/config.devel.yaml ) >/tmp/chainloop/cas.log 2>&1 &
fi

wait_for "control plane" http://127.0.0.1:8000/statusz 90
wait_for "artifact CAS"  http://127.0.0.1:8001/statusz 90
echo "chainloop stack is up (control plane :8000/:9000, CAS :8001/:9001, dex :5556, vault :8200)"
EOF

COPY --chmod=755 <<'EOF' /usr/local/bin/chainloop-stop
#!/bin/bash
pkill -x chainloop-controlplane 2>/dev/null || true
pkill -x chainloop-cas 2>/dev/null || true
pkill -x dex 2>/dev/null || true
pkill -x vault 2>/dev/null || true
service postgresql stop >/dev/null 2>&1 || true
true
EOF

# Smoke test: boot the whole stack once and confirm both servers answer /statusz, then tear it down.
# A failure is reported in the build log and does not abort the build.
RUN (chainloop-start \
      && echo "control plane /statusz:" && curl -fsS http://127.0.0.1:8000/statusz && echo \
      && echo "artifact CAS /statusz:" && curl -fsS http://127.0.0.1:8001/statusz && echo \
      && chainloop-stop) \
    || (echo "WARNING: stack smoke test failed"; tail -n 60 /tmp/chainloop/*.log 2>/dev/null; chainloop-stop; true)

# Everything is fetched. From here on the go command must not reach a proxy or download a toolchain,
# so a reproducer or patch built later also proves the image works with no network.
ENV GOPROXY=off \
    GOSUMDB=off

CMD ["bash"]
