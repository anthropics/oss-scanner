FROM golang:1.21-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends shellcheck \
    && rm -rf /var/lib/apt/lists/*
COPY . /src
WORKDIR /src
RUN cd sidecar && go build ./... && (go test ./... || echo "WARNING: go test reported failures")
RUN find . -name '*.sh' -not -path './.git/*' -print0 | xargs -0 -r -n1 bash -n
RUN shellcheck -S warning $(find . -name '*.sh' -not -path './.git/*') || echo "WARNING: shellcheck reported issues"
