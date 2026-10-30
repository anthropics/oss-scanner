FROM golang:1.26.7-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl git jq pkg-config procps sudo \
      iproute2 iptables nftables libpcap-dev softhsm2 sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN go mod download

# Build every server-side and agent binary. The desktop UI (client/ui) is skipped: it embeds a
# frontend bundle that needs a separate Node/pnpm build and is not a security boundary.
RUN go build -o /usr/local/bin/netbird ./client \
    && go build -o /usr/local/bin/netbird-mgmt ./management \
    && go build -o /usr/local/bin/netbird-signal ./signal \
    && go build -o /usr/local/bin/netbird-relay ./relay \
    && go build -o /usr/local/bin/netbird-proxy ./proxy \
    && go build -o /usr/local/bin/netbird-server ./combined

# Compile every test binary (including the pkcs11 and privileged tags) so the build cache is warm
# and reproducers can be compiled offline.
RUN go test -tags devcert -run '^$' $(go list -e ./... | grep -v -e /client/ui) >/dev/null \
    || echo 'WARNING: some test packages did not compile'
RUN go test -tags 'devcert privileged' -run '^$' $(go list -e ./client/... | grep -v -e /client/ui) >/dev/null \
    || echo 'WARNING: some privileged test packages did not compile'
RUN go test -tags pkcs11 -run '^$' ./client/internal/pkcs11/... ./client/internal/certproof/... >/dev/null \
    || echo 'WARNING: pkcs11 test packages did not compile'

# Run the cheap host-safe tests so the image is known to work, without failing the build.
RUN go test -tags devcert -short -p 4 -timeout 20m \
      $(go list -e ./... | grep -v -e /client/ui -e /e2e -e /integration_tests -e /client/testutil/privileged) \
    || echo 'WARNING: baseline unit tests reported failures'

# Reproducers and patches must build with the network disabled.
ENV GOPROXY=off \
    GOSUMDB=off

CMD ["bash"]
