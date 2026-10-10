# Match Melodix's Linux CI environment. The scanner copies the repository to /src.
FROM golang:1.26-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates git libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Fetch dependencies while network access is available during image build.
RUN go mod download

# Keep the build aligned with the project's CI and leave the source, tests,
# and built executables available for offline analysis in /src.
RUN go vet ./... \
    && go test -race ./... \
    && go build -o /src/melodix-discord ./cmd/discord/ \
    && go build -o /src/melodix-cli ./cmd/cli/
