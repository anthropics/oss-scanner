# syntax=docker/dockerfile:1
FROM debian:bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    OPENRESTY_PREFIX=/usr/local/openresty \
    PATH=/usr/local/openresty/bin:/usr/local/openresty/nginx/sbin:/usr/local/openresty/luajit/bin:$PATH \
    TEST_NGINX_BINARY=/usr/local/openresty/nginx/sbin/nginx \
    PERL5LIB=/opt/test-nginx/lib

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates curl wget git sudo cmake pkg-config \
      libyaml-dev libxml2-dev libxslt1-dev libldap2-dev libssl-dev \
      libpcre3-dev libpcre2-dev libbrotli-dev zlib1g-dev unzip cpanminus procps python3 \
      etcd-server etcd-client \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Follow upstream CI: debug APISIX runtime with its checked SHA-256, then LuaRocks.
RUN bash ci/linux-install-openresty.sh \
    && bash utils/linux-install-luarocks.sh

# Preserve successful dependency downloads if a registry request fails transiently.
RUN set -eu; \
    for attempt in 1 2 3; do \
        if make deps; then exit 0; fi; \
    done; \
    exit 1
RUN make install

# Match the Test::Nginx revision used by upstream CI. Keep test helpers offline.
RUN cpanm --notest Test::Nginx IPC::Run \
    && git init /opt/test-nginx \
    && git -C /opt/test-nginx remote add origin https://github.com/openresty/test-nginx.git \
    && git -C /opt/test-nginx fetch --depth=1 origin ced30a31bafab6c68873efb17b6d80f39bcd95f5 \
    && git -C /opt/test-nginx checkout --detach FETCH_HEAD \
    && git submodule update --init t/toolkit \
    && luarocks install lua-resty-openssl --tree deps

RUN <<'EOF'
cat > /usr/local/bin/oss-scanner-test <<'SCRIPT'
#!/bin/bash
set -euo pipefail
cd /src
etcd_dir=$(mktemp -d)
etcd --data-dir "$etcd_dir" \
    --listen-client-urls http://127.0.0.1:2379 \
    --advertise-client-urls http://127.0.0.1:2379 \
    > /tmp/oss-scanner-etcd.log 2>&1 &
etcd_pid=$!
trap 'kill "$etcd_pid" 2>/dev/null || true; wait "$etcd_pid" 2>/dev/null || true; rm -rf "$etcd_dir"' EXIT
ready=false
for attempt in {1..30}; do
    if ETCDCTL_API=3 etcdctl endpoint health >/dev/null 2>&1; then
        ready=true
        break
    fi
    sleep 1
done
if [ "$ready" != true ]; then
    cat /tmp/oss-scanner-etcd.log
    exit 1
fi
make init
FLUSH_ETCD=1 prove -I/opt/test-nginx/lib -I. \
    t/core/table.t t/core/json.t t/core/string.t t/core/schema_def.t
SCRIPT
chmod +x /usr/local/bin/oss-scanner-test
EOF

WORKDIR /src
CMD ["bash"]
