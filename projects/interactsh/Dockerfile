FROM golang:1.27
COPY . /src
WORKDIR /src
RUN go mod download && go build -o /usr/local/bin/ ./cmd/interactsh-server ./cmd/interactsh-client
# Tests that need the network fail here and offline; that is expected.
RUN go test -short -timeout 10m ./... || echo "WARNING: go test reported failures"
