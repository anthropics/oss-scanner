# syntax=docker/dockerfile:1.4
#
# Two ways in, selected by the `binaries` build context:
#
#   prebuilt — the CI job already compiled the release binaries and passes them
#              in. It builds inside this same `rust:bookworm` image, so the
#              glibc the binaries link against matches the runtime stage. That
#              skips a second full compile of the workspace.
#
#   builder  — nothing was passed in (a local `docker build`, or CI without the
#              artifact). Compiles from source, as before.
#
# Select with `--build-arg BINARIES=prebuilt`. Default is a self-contained build.
ARG BINARIES=builder

FROM rust:bookworm AS builder

RUN apt-get update && apt-get install --no-install-recommends -y protobuf-compiler libprotobuf-dev && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=shared_fixtures / /shared-fixtures
# copy manifests
COPY ./Cargo.toml .
COPY ./Cargo.lock .
COPY ./build.rs .
COPY ./rustfmt.toml .
COPY ./Makefile .
COPY ./docker/local/.env .
COPY ./docker/local/configuration.yaml .
COPY .sqlx .sqlx/
COPY ./proto ./proto
COPY ./tests/bdd.rs ./tests/bdd.rs

# build this project to cache dependencies
#RUN sqlx database create && sqlx migrate run

# build skeleton and remove src after
#RUN cargo build --release; \
#    rm src/*.rs


COPY ./src ./src
COPY ./crates ./crates
COPY ./scenarios ./scenarios

# for ls output use BUILDKIT_PROGRESS=plain docker build .
#RUN ls -la /app/ >&2
#RUN sqlx migrate run
#RUN cargo sqlx prepare -- --bin stacker
ENV SQLX_OFFLINE=true

RUN apt-get update && apt-get install --no-install-recommends -y libssl-dev; \
    cargo build --release --bin server; \
    cargo build --release --bin console --features explain; \
    cargo build --release --bin cleanup-notify; \
    cargo build --release --bin backfill_field_policy

#RUN ls -la /app/target/release/ >&2

# Config files and the sqlx CLI, needed by both paths. Separate from `builder`
# so the prebuilt path does not drag in a compile of the workspace just to get
# two YAML files.
FROM rust:bookworm AS config
RUN cargo install sqlx-cli --no-default-features --features rustls,postgres
WORKDIR /app
COPY ./docker/local/.env .
COPY ./docker/local/configuration.yaml .

# The two sources of binaries, each putting them at the image root so the
# production stage copies from one place regardless of which was used.

# Handed in by CI, already compiled in this same rust:bookworm image.
FROM scratch AS prebuilt-source
COPY --from=prebuilt_binaries / /

FROM scratch AS builder-source
COPY --from=builder /app/target/release/server /server
COPY --from=builder /app/target/release/console /console
COPY --from=builder /app/target/release/cleanup-notify /cleanup-notify
COPY --from=builder /app/target/release/backfill_field_policy /backfill_field_policy

FROM ${BINARIES}-source AS binaries

# deploy production
FROM debian:bookworm-slim AS production

RUN apt-get update && apt-get install --no-install-recommends -y libssl-dev ca-certificates;
# create app directory
WORKDIR /app
RUN mkdir ./files && chmod 0777 ./files

# copy binary and configuration files
COPY --from=binaries /server .
COPY --from=binaries /console .
COPY --from=binaries /cleanup-notify .
COPY --from=binaries /backfill_field_policy .
COPY --from=config /app/.env .
COPY --from=config /app/configuration.yaml .
COPY --from=config /usr/local/cargo/bin/sqlx /usr/local/bin/sqlx
COPY ./access_control.conf.dist ./access_control.conf
# Migrations ship in the image so a fresh environment can bring its own schema
# up. See docker/entrypoint.sh: without 20260828121000 the server cannot
# resolve a template at all.
COPY ./migrations ./migrations
COPY ./docker/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

EXPOSE 8000

# apply migrations, then run the binary
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/app/server"]
