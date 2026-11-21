# Source at /src plus every Go module, so reproducers and patches build offline. Embedded assets (CA bundle, SELinux
# policy, iPXE binaries) are committed, so the plain Go toolchain builds Talos without the BuildKit release pipeline.
FROM docker.io/library/golang:1.27-trixie

ENV CGO_ENABLED=0 \
    GOFLAGS=-tags=tcell_minimal,grpcnotrace,no_siderov1_auth

COPY . /src
WORKDIR /src

# Root module and pkg/machinery of the go.work workspace. A newer Go requested by go.mod is fetched into the module
# cache here too.
RUN go mod download && (cd pkg/machinery && go mod download)

ENV GOPROXY=off \
    GOSUMDB=off
