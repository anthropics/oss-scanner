FROM golang:1.27.2-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl git iproute2 jq pkg-config procps sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# The scanner supplies the Headscale checkout as the build context.
# Keep the source, Go toolchain, and dependency caches in the final image.
COPY . /src
WORKDIR /src

RUN go mod download \
    && go build -o /usr/local/bin/headscale ./cmd/headscale

# Keep tests available to the scanner even if a baseline test fails.
# External CLI/provider suites have no -short guard; run the Go client separately.
RUN go test -short -p 4 -parallel 4 -timeout 20m \
      -skip '^(TestAPIv2|TestAPIv2OAuthScopes)$' ./hscontrol/... \
    || echo 'WARNING: control-plane baseline tests failed'
RUN go test -short -p 2 -parallel 2 -timeout 10m \
      -run '^TestAPIv2$/^GoClient$' ./hscontrol/servertest \
    || echo 'WARNING: API Go-client tests failed'

# New reproducers and patches must also build with the network disabled.
ENV GOPROXY=off \
    GOSUMDB=off

CMD ["bash"]
