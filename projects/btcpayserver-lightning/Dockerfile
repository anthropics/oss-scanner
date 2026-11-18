# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:10.0.403-noble

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE=true \
    NUGET_XMLDOC_MODE=skip

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git jq openssl \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Build every library target and the test project before network access is removed.
RUN dotnet restore BTCPayServer.Lightning.sln -p:NuGetAudit=false --verbosity minimal \
    && dotnet build BTCPayServer.Lightning.sln --no-restore --configuration Debug \
        --disable-build-servers --verbosity minimal -m:2 \
    && dotnet build-server shutdown

RUN <<'SETUP'
cat > /usr/local/bin/btcpayserver-lightning-oss-test <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
cd /src
# These tests use local fixtures, injected handlers, or loopback RPC servers.
filter='FullyQualifiedName~AsycLockTests|FullyQualifiedName~JsonTests'
filter+='|FullyQualifiedName~PhoenixdConnectionStringTests|FullyQualifiedName~WebSocketHttpClientTests'
filter+='|FullyQualifiedName~CLightningTests|FullyQualifiedName~CLightningPayTests'
filter+='|FullyQualifiedName~CommonTests.CanParse|FullyQualifiedName~CommonTests.RejectsInvalidBOLT11Amounts'
filter+='|FullyQualifiedName~CommonTests.CanUseLightMoney|FullyQualifiedName~CommonTests.LightMoneyOverflowTest'
timeout 300 dotnet test tests/BTCPayServer.Lightning.Tests.csproj \
    --no-build --no-restore --configuration Debug \
    --filter "$filter" --verbosity minimal
dotnet build-server shutdown
SCRIPT
chmod +x /usr/local/bin/btcpayserver-lightning-oss-test
SETUP

CMD ["bash"]
