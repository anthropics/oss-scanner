# Scanner image for https://github.com/extphprs/ext-php-rs (master).
#
# The audit runs offline, so this build compiles a debug PHP (ZEND_DEBUG assertions on) with the embed SAPI, fetches
# every crate, and builds the workspace and its test binaries with the feature set the repository's embed CI lane uses.
# threat_model.md, next to this file, says how to run them.
FROM rust:1-bookworm
ENV DEBIAN_FRONTEND=noninteractive
# libclang is for bindgen, which generates the Zend bindings from the PHP headers at build time. bison and re2c build PHP.
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang libclang-dev bison re2c pkg-config \
    && rm -rf /var/lib/apt/lists/*

# PHP from source, debug build, with libphp.so for the embed tests. --disable-all keeps the core and the always-on
# extensions (pcre, spl, reflection, random), which is all the integration tests use.
ARG PHP_VERSION=8.5.11
ARG PHP_SHA256=338630ba9450f0b938bef8d740162c61c33bf64a1b421c6333c01df8a9fdb0ab
RUN curl -fsSL -o /tmp/php.tar.gz "https://www.php.net/distributions/php-${PHP_VERSION}.tar.gz" \
    && echo "${PHP_SHA256}  /tmp/php.tar.gz" | sha256sum -c - \
    && mkdir /opt/php-src && tar -xzf /tmp/php.tar.gz -C /opt/php-src --strip-components=1 && rm /tmp/php.tar.gz \
    && cd /opt/php-src \
    && ./configure --enable-debug --enable-embed --disable-all --disable-cgi --disable-phpdbg \
         CFLAGS="-g -fno-omit-frame-pointer" \
    && make -j"$(nproc)" && make install && ldconfig \
    && php -v

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The embed feature links with -lphp, and rust-lld does not search /usr/local/lib on its own. LIBRARY_PATH reaches
# every link, doctests included, where RUSTFLAGS does not.
ENV RUST_BACKTRACE=1 \
    CARGO_TERM_COLOR=never \
    LIBRARY_PATH=/usr/local/lib

ARG FEATURES=closure,embed,anyhow,smartstring,observer,indexmap

RUN cargo fetch

# The workspace, the examples and every test binary, in the dev profile (debug assertions and overflow checks on). The
# integration tests build the tests crate cdylib and load it into php. A step that fails fails the build, and
# primary_contact gets the log.
RUN cargo build --workspace --features "${FEATURES}" --lib --bins --examples \
    && cargo test --workspace --features "${FEATURES}" --no-run

# Run the tests so the log shows the image works, without letting a failure abort the build.
RUN timeout 1800 cargo test --workspace --features "${FEATURES}" --no-fail-fast \
    || echo "WARNING: cargo test reported failures"

# Everything is fetched. From here on cargo must not try to reach a registry.
ENV CARGO_NET_OFFLINE=true
