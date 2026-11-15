# Scanner image for https://github.com/openfga/openfga (main).
#
# The audit runs offline, so this build fetches every Go module, builds the server and its tests (with and without
# -race), installs the `fga` CLI and grpcurl for talking to a running server, and prepares a local PostgreSQL cluster
# and a SQLite file that are already migrated to the current schema. threat_model.md, next to this file, says how to
# use each of them.

# go.mod sets `go 1.26.0`; CI uses the version go.mod names.
FROM golang:1.26-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1

# sqlite3 and postgresql to inspect and run the SQL datastores; curl and jq for the HTTP API. MySQL is not packaged
# for Debian, so the MySQL datastore can be read but not run here.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git jq procps sqlite3 postgresql postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Clients: `fga` converts DSL models to JSON and drives every API; grpcurl speaks gRPC to port 8081.
RUN GOBIN=/usr/local/bin go install github.com/openfga/cli/cmd/fga@v0.8.2 \
    && GOBIN=/usr/local/bin go install github.com/fullstorydev/grpcurl/cmd/grpcurl@v1.9.4

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# From here on use the toolchain in the image, never a downloaded one.
ENV GOTOOLCHAIN=local

# The server, and every package's tests compiled with and without the race detector so the build cache is warm
# offline. Mocks are checked in, so `make generate-mocks` (which installs mockgen) is not needed. A step that fails
# fails the build, and primary_contact gets the log.
RUN go mod download \
    && go build -o /usr/local/bin/openfga ./cmd/openfga \
    && go test -run '^$' ./... \
    && go test -race -run '^$' ./...

# A migrated PostgreSQL database (user postgres, password `password`, database `openfga`) and a migrated SQLite file,
# so the server can run against a SQL datastore offline. Start PostgreSQL with `service postgresql start`.
RUN service postgresql start \
    && su postgres -c "psql -q -c \"ALTER USER postgres PASSWORD 'password';\"" \
    && su postgres -c "createdb openfga" \
    && openfga migrate --datastore-engine postgres \
         --datastore-uri 'postgres://postgres:password@127.0.0.1:5432/openfga?sslmode=disable' \
    && service postgresql stop \
    && mkdir -p /var/lib/openfga \
    && openfga migrate --datastore-engine sqlite --datastore-uri 'file:/var/lib/openfga/openfga.db'

# The tests that need no Docker, so the log shows the image works without letting a failure abort the build. The
# repository's PostgreSQL and MySQL test fixtures start containers through the Docker API, which does not exist here:
# the packages that test only those engines are left out, and the Postgres and MySQL cases inside the others fail fast.
RUN (timeout 1800 go test -count=1 -p 4 -timeout 25m \
       $(go list ./... | grep -vE '/pkg/storage/(mysql|postgres|migrate)$|/cmd/(migrate|validatemodels)$|/openfga/tests/') \
       || echo "WARNING: go test reported failures (Postgres/MySQL cases need Docker and are expected to fail)") \
    && (timeout 1200 go test -count=1 -timeout 20m -run 'Memory|SQLite' ./tests/... \
       || echo "WARNING: matrix tests reported failures")

# Everything is fetched. From here on the go command must not try to reach a proxy.
ENV GOPROXY=off \
    GOSUMDB=off

CMD ["bash"]
