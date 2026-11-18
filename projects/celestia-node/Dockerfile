FROM golang:1.26.8-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git make wget \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN for i in 1 2 3; do go mod download && break; sleep 10; done && go mod download

# The Tastora end-to-end suite in nodebuilder/tests/tastora is a separate Go module.
RUN cd nodebuilder/tests/tastora \
    && for i in 1 2 3; do go mod download && break; sleep 10; done && go mod download

# The celestia node binary (build/celestia), plus the cel-key and cel-shed utilities.
RUN make build cel-key cel-shed

# Compile every test binary, including the integration tags and the Tastora module, so offline runs only relink.
# The fibre_e2e Tastora test does not compile against the pinned celestia-app on main, so it is left out.
RUN go test -tags fibre -run '^$' ./... \
    && go test -tags integration,fibre -run '^$' ./nodebuilder/tests/... \
    && cd nodebuilder/tests/tastora \
    && go test -tags integration -run '^$' ./...

RUN (go test -tags fibre -timeout 15m ./header/... ./share/... ./blob/... ./das/... ./store/... \
        ./api/... ./libs/... ./pruner/... \
        || echo "WARNING: unit tests reported failures") \
    && git status --short

ENV GOPROXY=off \
    GOFLAGS=-mod=readonly
