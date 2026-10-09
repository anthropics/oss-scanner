# OSS Scanner build for PerformanceStudio (C# / .NET 10): the Avalonia desktop app (PlanViewer.App), the CLI, the
# shared core library, the Blazor WebAssembly viewer, the PlanShare server and the SSMS extension projects.
#
# Base image: Microsoft's .NET SDK image. The repository's global.json does not pin an SDK (it only selects the test
# runner), so this tag is the pin: a 10.0 SDK, the same tag the sibling PerformanceMonitor project builds with.
FROM mcr.microsoft.com/dotnet/sdk:10.0.401

ENV DEBIAN_FRONTEND=noninteractive \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the whole solution as the repository's ubuntu CI job does (.github/workflows/ci.yml): the WebAssembly workload,
# restore, build. Debug configuration keeps symbols and line numbers complete.
RUN dotnet workload install wasm-tools \
    && dotnet restore PlanViewer.sln \
    && dotnet build PlanViewer.sln -c Debug --no-restore

# Run the core test project as ci.yml does, but do not let a failing test abort the build. The SSMS installer tests
# target net472 and are not run on Linux.
RUN (dotnet test tests/PlanViewer.Core.Tests/PlanViewer.Core.Tests.csproj -c Debug --no-build \
      -- --hangdump --hangdump-timeout 5m --hangdump-type none \
    || echo "WARNING: PlanViewer.Core.Tests reported failures")
