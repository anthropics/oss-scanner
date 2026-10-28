# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:10.0.402-noble

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE=true \
    NUGET_XMLDOC_MODE=skip \
    MSBUILDDISABLENODEREUSE=1 \
    CI_TESTS=true

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git jq postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN dotnet restore btcpayserver.sln -p:NuGetAudit=false --verbosity minimal \
    && dotnet build btcpayserver.sln --no-restore --configuration Debug \
        --disable-build-servers --verbosity minimal -m:2 \
    && dotnet build-server shutdown

RUN <<'SETUP'
cat > /usr/local/bin/btcpayserver-oss-test <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
cd /src
timeout 900 dotnet test --project BTCPayServer.Tests/BTCPayServer.Tests.csproj \
    --no-build --no-restore --configuration Debug \
    --filter "Fast=Fast&FullyQualifiedName!~ThirdPartyTests.CheckJsContent" \
    --verbosity minimal
dotnet build-server shutdown
SCRIPT
chmod +x /usr/local/bin/btcpayserver-oss-test
SETUP

CMD ["bash"]
