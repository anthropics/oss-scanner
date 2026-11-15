FROM rust:1

RUN rustup component add clippy rustfmt && rustup install nightly && rustup component add miri --toolchain nightly rust-src
RUN apt update && apt install -y libmariadb-dev-compat libpq-dev libsqlite3-dev postgresql mariadb-server cmake

COPY . /src
WORKDIR /src
RUN cargo fetch && (cd fuzz && cargo fetch) && (cd diesel_compile_tests && cargo fetch) && \
    cargo fetch --manifest-path diesel_compile_tests/tests/Cargo.toml && \
    cargo +nightly -Z build-std fetch && \
    cargo install cargo-nextest --locked && cargo install cargo-fuzz

ENV CARGO_NET_OFFLINE=true


RUN cat > /src/.env <<EOF
PG_DATABASE_URL=postgres://postgres:postgres@localhost/diesel_tests 
SQLITE_DATABASE_URL=":memory:" 
MYSQL_DATABASE_URL=mysql://mariadb:mariadb@127.0.0.1/diesel_tests 
MYSQL_UNIT_TEST_DATABASE_URL=mysql://mariadb:mariadb@127.0.0.1/diesel_unit_test 
MARIADB_DATABASE_URL=mariadb://mariadb:mariadb@127.0.0.1/diesel_tests 
MARIADB_UNIT_TEST_DATABASE_URL=mariadb://mariadb:mariadb@127.0.0.1/diesel_unit_test 
EOF


RUN cat > /bin/startup.sh <<EOF
#!/bin/sh 
service postgresql start 
service mariadb start 
su - postgres -c "psql -c \"alter user postgres with password 'postgres' \""
su - postgres -c "createdb diesel_tests -O postgres"
mysql -e "create user mariadb@localhost identified by 'mariadb'; create database diesel_tests; create database diesel_unit_test; GRANT ALL PRIVILEGES ON *.* TO 'mariadb'@'localhost';"
exec "/usr/bin/bash" 
EOF

RUN chmod +x /bin/startup.sh && sed -i 's/^# *\(en_US.UTF-8\)/\1/' /etc/locale.gen && locale-gen

ENTRYPOINT /bin/startup.sh
