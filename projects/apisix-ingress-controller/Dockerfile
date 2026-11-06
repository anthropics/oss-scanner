# syntax=docker/dockerfile:1
FROM golang:1.26-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git make build-essential python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN go mod download
RUN go build -mod=readonly -o bin/apisix-ingress-controller cmd/main.go
RUN make envtest
# The upstream-pinned setup tool defaults to the retired GCS bucket.
RUN set -eu; mkdir -p /opt/envtest; \
    for attempt in 1 2 3; do \
        if bin/setup-envtest --use-deprecated-gcs=false use 1.30.0 \
            --bin-dir /opt/envtest -p path > /opt/envtest-path; then exit 0; fi; \
    done; \
    exit 1

# The repository's AGENTS.md points to this shared, externally maintained model.
# Cache the documentation during setup so the audit can consult it offline.
RUN curl --fail --location --retry 3 \
      https://raw.githubusercontent.com/apache/apisix/master/docs/en/latest/security-threat-model.md \
      -o /opt/apisix-threat-model.md

# Use the same package exclusions as upstream's Makefile. Compile test dependencies
# online; cluster E2E, conformance, and benchmark environments are not provisioned.
RUN go list ./... > /opt/oss-scanner-all-packages \
    && sed -E '\@/(e2e|conformance|benchmark)(/|$)@d' /opt/oss-scanner-all-packages > /opt/oss-scanner-test-packages \
    && test -s /opt/oss-scanner-test-packages \
    && KUBEBUILDER_ASSETS="$(cat /opt/envtest-path)" \
       go test -mod=readonly -p 2 -run '^$' $(cat /opt/oss-scanner-test-packages)

RUN <<'EOF'
cat > /usr/local/bin/oss-scanner-test <<'SCRIPT'
#!/bin/bash
set -euo pipefail
cd /src
export GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off
export KUBEBUILDER_ASSETS="$(cat /opt/envtest-path)"
mapfile -t packages < /opt/oss-scanner-test-packages
test "${#packages[@]}" -gt 0
go test -mod=readonly -count=1 -p 2 -timeout 10m "${packages[@]}"
SCRIPT
chmod +x /usr/local/bin/oss-scanner-test
EOF

WORKDIR /src
CMD ["bash"]
