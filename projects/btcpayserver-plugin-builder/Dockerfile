# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:10.0.403-noble

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE=true \
    NUGET_XMLDOC_MODE=skip

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates coreutils curl git jq openssl python3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Include the public application, broker, shared contracts, tests, and test fixtures.
RUN dotnet restore btcpayserver-plugin-builder.sln -p:NuGetAudit=false --verbosity minimal \
    && dotnet build btcpayserver-plugin-builder.sln --no-restore --configuration Debug \
        --disable-build-servers --verbosity minimal -m:2 \
    && dotnet build-server shutdown

RUN <<'SETUP'
cat > /usr/local/bin/btcpayserver-plugin-builder-oss-test <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
cd /src
# Explicitly select tests using temporary fixtures, fake Docker, or local HTTP servers.
classes=(
    AdminApiDocumentationTests AdminEventEmailTests AdminWebhookTests ApiAccessLogTests
    AzureStagedUploadContractTests BrokerDockerMonitorTests BtcMapsServiceTests
    BtcPayHostVersionParserTests BuildBrokerSecurityTests BuildDependencyBoundaryTests
    BuildExecutorOptionsTests BuildExecutorStateTests BuildSandboxContractTests
    BuildScratchCleanerTests BuildWorkerAssetTests DockerBuildSandboxLifecycleTests
    DockerStartupIsolationTests EmailServiceTests ExternalAccountVerificationServiceTests
    GitHostingProviderTests GithubServiceTests PluginBuilderOptionsTests
    PluginSlugModelBinderTests ProcessRunnerTests PublisherApiDocumentationTests
    RemoteBuildSandboxTests TurnstileVerifierTests
)
filter=''
for test_class in "${classes[@]}"; do
    filter+="${filter:+|}FullyQualifiedName~PluginBuilder.Tests.${test_class}."
done
timeout 900 dotnet test PluginBuilder.Tests/PluginBuilder.Tests.csproj \
    --no-build --no-restore --configuration Debug \
    --filter "($filter)&Category!=ExecutorIntegration" --verbosity minimal
dotnet build-server shutdown
SCRIPT
chmod +x /usr/local/bin/btcpayserver-plugin-builder-oss-test
SETUP

CMD ["bash"]
