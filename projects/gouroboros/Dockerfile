FROM golang:1.26.9-bookworm

WORKDIR /src
COPY . /src

RUN find /src -path /src/.git -prune -o -type f -name go.mod -print \
    | while IFS= read -r go_mod; do \
        module_dir="${go_mod%/go.mod}"; \
        (cd "$module_dir" && go mod download && go build ./...); \
      done
