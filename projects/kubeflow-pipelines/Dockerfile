FROM golang:1.27.4-bookworm@sha256:4fa7c968ba93f1635670522dbb01a2c78150443e1385746924566079f36570ea

WORKDIR /src
COPY . .
RUN go mod download all
RUN go build -mod=readonly -o /usr/local/bin/kfp-apiserver ./backend/src/apiserver
