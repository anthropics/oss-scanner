FROM golang:1.27

ENV CGO_ENABLED=1

# The scanner needs the checkout and toolchain after network access is removed.
COPY . /src
WORKDIR /src

RUN go mod download \
    && cd test && go mod download

# Keep debug symbols; go-nvml requires CGO even when no GPU is present.
RUN make build \
    && useradd --create-home scanner \
    && chown -R scanner:scanner /src /go \
    && git config --system --add safe.directory /src \
    && runuser -u scanner -- make test
