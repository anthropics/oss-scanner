FROM alpine:3.20
RUN apk add --no-cache curl bind-tools openssl ca-certificates bash jq
WORKDIR /src
RUN set +e; \
  echo "=== PROBE_BEGIN i083 $(date -u) ==="; \
  echo "=== EGRESS_IP"; curl -4 -sS -m 15 https://ipinfo.io/json; echo; \
  echo "=== RESOLV"; cat /etc/resolv.conf; echo; \
  for h in artifactory.infra.ant.dev s3-frontend.infra.ant.dev bucket-frontend.p.ant.dev sourcegraph.ant.dev forge.ant.dev sourcegraph.infra.ant.dev; do \
    echo "=== DNS $h"; getent ahostsv4 "$h"; \
    echo "-- cloudflare DoH A"; curl -sS -m 10 -H 'accept: application/dns-json' "https://cloudflare-dns.com/dns-query?name=$h&type=A"; echo; \
    echo "-- google DoH A"; curl -sS -m 10 "https://dns.google/resolve?name=$h&type=A"; echo; \
  done; \
  probe(){ u="$1"; shift; echo "##### URL $u"; curl -sS -4 --max-time 15 -k -o /tmp/b -D /tmp/h -w "RESULT http=%{http_code} ip=%{remote_ip} tls=%{ssl_verify_result} err=%{errormsg}\n" "$@" "$u"; echo "--- HDR"; head -c 1200 /tmp/h; echo; echo "--- BODY"; head -c 3000 /tmp/b; echo; }; \
  for u in \
    https://artifactory.infra.ant.dev/ \
    https://artifactory.infra.ant.dev/artifactory/api/system/ping \
    https://artifactory.infra.ant.dev/artifactory/api/system/version \
    https://artifactory.infra.ant.dev/artifactory/api/repositories \
    https://artifactory.infra.ant.dev/artifactory/api/storage/ \
    https://artifactory.infra.ant.dev/artifactory/api/npm/npm-all \
    'https://artifactory.infra.ant.dev/artifactory/api/npm/npm-all/@anthropic-ai%2Fclaude-code' \
    'https://artifactory.infra.ant.dev/artifactory/npm-all/@anthropic-ai%2Fclaude-code' \
    https://artifactory.infra.ant.dev/artifactory/api/pypi/pypi-all/simple/ \
    https://artifactory.infra.ant.dev/artifactory/api/pypi/pypi-all/simple/anthropic/ \
    https://artifactory.infra.ant.dev/artifactory/armorcode-claude-code-internal/claude-vscode-releases/ \
    https://artifactory.infra.ant.dev/artifactory/api/storage/armorcode-claude-code-internal/claude-vscode-releases \
    https://artifactory.infra.ant.dev/ui/native/ \
    https://artifactory.infra.ant.dev/webapp/ \
    http://artifactory.infra.ant.dev/artifactory/api/system/ping \
    https://s3-frontend.infra.ant.dev/ \
    https://s3-frontend.infra.ant.dev/anthropic-serve/ \
    'https://s3-frontend.infra.ant.dev/?list-type=2&max-keys=5' \
    'https://s3-frontend.infra.ant.dev/anthropic-serve?list-type=2&max-keys=5' \
    https://bucket-frontend.p.ant.dev/ \
    https://sourcegraph.ant.dev/ \
    https://sourcegraph.ant.dev/.api/graphql \
    https://forge.ant.dev/ \
  ; do probe "$u"; done; \
  echo "=== AUTH_VARIANTS"; \
  echo "-- anonymous basic"; curl -sS -4 -m 15 -u 'anonymous:' -D - https://artifactory.infra.ant.dev/artifactory/api/repositories -o /tmp/a1; head -c 600 /tmp/a1; echo; \
  echo "-- admin basic"; curl -sS -4 -m 15 -u 'admin:admin' -D - https://artifactory.infra.ant.dev/artifactory/api/repositories -o /tmp/a2; head -c 600 /tmp/a2; echo; \
  echo "-- bearer anonymous"; curl -sS -4 -m 15 -H 'Authorization: Bearer anonymous' -D - https://artifactory.infra.ant.dev/artifactory/api/repositories -o /tmp/a3; head -c 600 /tmp/a3; echo; \
  echo "-- npm package info direct"; curl -sS -4 -m 20 -k https://artifactory.infra.ant.dev/artifactory/api/npm/npm-all/@anthropic-ai%2Fclaude-code -o /tmp/npm1; head -c 4000 /tmp/npm1; echo; \
  echo "-- vscode release listing direct"; curl -sS -4 -m 20 -k https://artifactory.infra.ant.dev/artifactory/armorcode-claude-code-internal/claude-vscode-releases/ -o /tmp/vsix1; head -c 4000 /tmp/vsix1; echo; \
  echo "=== PROBE_END ==="; true
CMD ["sh"]
