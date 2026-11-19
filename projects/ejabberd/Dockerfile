# Debug build of ejabberd for OSS Scanner, on Erlang/OTP 28 (the version upstream CI uses) and Debian stable.
#
#   /src/_build/default/lib/*        every application, with debug_info; NIFs and port programs in priv/lib, built -g
#   /src/_build/dev/rel/ejabberd     development release: bin/ejabberdctl, conf/ejabberd.yml, the test certificates
#   /src/_build/test                 test profile, compiled for Common Test, with meck; `make test` starts at once
FROM erlang:28
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      libexpat1-dev libgd-dev libpam0g-dev libsqlite3-dev libssl-dev libwebp-dev libyaml-dev zlib1g-dev unzip \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Configured like upstream CI (.github/actions/manage-ejabberd): --enable-all without Elixir. The C flags reach the
# NIFs of the deps (fast_xml, fast_tls, stringprep, ...).
RUN ./autogen.sh \
    && ./configure --with-rebar=./rebar3 --enable-all --disable-elixir CFLAGS="-g -O2 -fno-omit-frame-pointer" \
    && make \
    && make dev

# Only the back ends that need no database server; a plain `make test` in the image uses the same list.
ENV CT_BACKENDS=agnostic,mnesia,sqlite,ldap,extauth

# Fetches the test-only deps and leaves the test profile compiled the way `make test` wants it. Failures must not
# fail the build, and the bound keeps a hung test from using up the build's time.
RUN timeout 1500 make test || echo "WARNING: common test reported failures"
