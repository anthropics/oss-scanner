# OSS Scanner build for PerformanceMonitor (C# / .NET 10): the Lite and Dashboard WPF apps, the Darling headless
# service, the shared libraries, the deprecated Installer, and the PostgreSQL store code. The T-SQL install scripts
# under install/ are plain files in the checkout and need no build.
#
# Base image: Microsoft's .NET SDK image, pinned to the exact SDK in the repository's global.json (10.0.401, the
# same pin the project's own Darling/Dockerfile uses). Bump this tag together with global.json.
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

# Build every project in the solution as the maintainers do (Debug, as in the repository's CLAUDE.md, so symbols and
# line numbers are complete). The WPF projects (Lite, Dashboard, PerformanceMonitor.Ui, the Darling Viewer and the
# test projects) target net10.0-windows. They compile on Linux against the Windows reference packs that
# EnableWindowsTargeting downloads, but they cannot run here. The Darling service and the libraries are plain
# net10.0 and run on Linux (the repository's "Darling Linux build" CI job publishes the service for linux-x64).
RUN dotnet restore PerformanceMonitor.sln -p:EnableWindowsTargeting=true \
    && dotnet build PerformanceMonitor.sln -c Debug --no-restore -p:EnableWindowsTargeting=true

# The Darling service, published for linux-x64 as the repository's "Darling Linux build" job does, but in the Debug
# configuration so the PDBs stay beside the binaries. Run it with:
#   dotnet /opt/darling/PerformanceMonitor.Darling.Service.dll
RUN dotnet publish Darling/PerformanceMonitor.Darling.Service/PerformanceMonitor.Darling.Service.csproj \
      -c Debug -r linux-x64 --self-contained false -o /opt/darling

# Tests: the three runnable suites (Darling.Tests, Lite.Tests, Dashboard.Tests) target net10.0-windows with WPF, so
# they are compiled above but cannot execute on Linux. Installer.Tests needs a SQL Server instance. No tests run in
# this image.
