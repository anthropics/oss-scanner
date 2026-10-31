# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:10.0.402-noble

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE=true \
    NUGET_XMLDOC_MODE=skip \
    MSBUILDDISABLENODEREUSE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl gettext-base git gnupg gzip jq nginx openssl \
    python3 rsync shellcheck tar unzip util-linux zip \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN dotnet restore docker-compose-generator/src/docker-compose-generator.csproj \
        -p:NuGetAudit=false --verbosity minimal \
    && dotnet build docker-compose-generator/src/docker-compose-generator.csproj \
        --no-restore --configuration Debug --disable-build-servers \
        --verbosity minimal -m:2 \
    && dotnet build-server shutdown \
    && find . -type f -name '*.sh' -exec bash -n {} +

RUN <<'SETUP'
cat > /usr/local/bin/btcpayserver-docker-oss-test <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
cd /src
tests=(
    tests/btcpay-routes-test.sh
    tests/build-test.sh
    tests/btcpay-fragments-test.sh
    tests/btcpay-switch-test.sh
    tests/environment-test.sh
    tests/generate-secrets-test.sh
    tests/backup-test.sh
    tests/restore-test.sh
)
for test_script in "${tests[@]}"; do
    timeout 600 bash "$test_script"
done
SCRIPT
chmod +x /usr/local/bin/btcpayserver-docker-oss-test
SETUP

RUN btcpayserver-docker-oss-test

CMD ["bash"]
