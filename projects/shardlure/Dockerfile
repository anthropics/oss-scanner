# ShardLure is one Go module (cmd/shardlure) plus Python installer/persona scripts (scripts/, install/persona/).
# The scanner builds this with the ShardLure checkout as the build context.
FROM golang:1.27-bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    GOFLAGS=-mod=mod \
    GOTOOLCHAIN=local \
    CGO_ENABLED=0
# python3 + rsync: installer and persona-patch unit tests (apply-stealth.sh syncs with rsync); nodejs: the dashboard JS behaviour tests
# (internal/web/campaign_node_harness_test.go skips loudly without node).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 python3-yaml nodejs sqlite3 rsync \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Fetch every module now: the audit runs without network.
RUN go mod download && go mod verify

# Build as the maintainers build it (make build), keeping DWARF and symbols.
RUN go build -o /src/shardlure ./cmd/shardlure && /src/shardlure version

# Cheap checks so the image is known good; failures are reported, not fatal.
RUN (go vet ./... && go test ./... -count=1 -timeout 20m) || echo "WARNING: go vet/test reported failures"
RUN (python3 -m unittest $(ls scripts/test_*.py | sed 's#\.py##;s#/#.#')) || echo "WARNING: Python unit tests reported failures"
