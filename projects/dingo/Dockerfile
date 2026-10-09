FROM golang:1.26.9-bookworm

WORKDIR /src
COPY . /src

RUN go mod download && make build
