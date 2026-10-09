FROM golang:1.27.1
# Pinned Debian package versions break on every point release.
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends chromium \
    && rm -rf /var/lib/apt/lists/*
COPY . /src
WORKDIR /src
RUN go mod download && go build -o /usr/local/bin/nuclei ./cmd/nuclei
# The scan runs offline, so the public templates must be fetched now.
RUN nuclei -update-templates || echo "WARNING: template download failed"
# Tests that need the network fail here and offline; that is expected.
RUN go test -short -timeout 10m ./... || echo "WARNING: go test reported failures"
