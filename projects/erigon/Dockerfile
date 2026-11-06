##  Erigon build for OSS Scanner.
##  Build context is the Erigon checkout; network is available only here.
##  Toolchain and build tags follow the release image (erigon's root Dockerfile).
FROM golang:1.27-trixie

ENV CGO_ENABLED=1 \
    GOTOOLCHAIN=local \
    GODEBUG=cgocheck=0

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN go mod download

# Binaries in scope, built as releases build them (symbols kept): /src/build/bin/{erigon,capcli,downloader,integration}
RUN make BUILD_TAGS=nosqlite,noboltdb erigon capcli downloader integration
ENV PATH=/src/build/bin:$PATH

# Pre-compile all test binaries so reproducers build and run offline on the 2-CPU scan agent.
RUN go test -run '^$' ./... > /tmp/test-compile.log 2>&1 \
    || { tail -50 /tmp/test-compile.log; echo 'WARNING: some test packages failed to compile'; }

# Smoke tests on the most exposed parsers; never fail the build on them.
RUN go test -short -timeout 15m \
      ./execution/rlp/... ./execution/types/... ./p2p/... ./rpc/... ./cl/ssz/... \
    || echo 'WARNING: baseline tests reported failures'

# Reproducers and patches must build with the network disabled.
ENV GOPROXY=off \
    GOSUMDB=off

CMD ["bash"]