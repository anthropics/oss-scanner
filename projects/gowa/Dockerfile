FROM golang:1.26-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=1 \
    GOTOOLCHAIN=local \
    TZ=UTC

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential git ca-certificates ffmpeg webp poppler-utils tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src/src

RUN go mod download \
    && go build -o /usr/local/bin/whatsapp . \
    && go test -run '^$' ./...

CMD ["/bin/bash"]
