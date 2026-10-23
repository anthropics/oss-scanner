FROM rust:1

RUN apt-get update && apt-get install -y --no-install-recommends postgresql && rm -rf /var/lib/apt/lists/*
COPY . /src
WORKDIR /src
RUN cargo fetch
ENV WTX_DATABASE_URI_POSTGRES=postgres://wtx_scram:wtx@localhost:5432/wtx
RUN service postgresql start \
 && su postgres -c "psql -v ON_ERROR_STOP=1 -c \"SET password_encryption TO 'scram-sha-256'; CREATE ROLE wtx_scram PASSWORD 'wtx' CREATEDB LOGIN;\"" \
 && su postgres -c "createdb -O wtx_scram wtx" \
 && cargo test --all-features -- --test-threads=1
