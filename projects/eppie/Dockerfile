FROM mcr.microsoft.com/dotnet/aspnet:8.0-noble AS net8
FROM mcr.microsoft.com/dotnet/sdk:10.0-noble

# TuviCore's tests target .NET 8; Eppie's desktop app and ViewModels tests use .NET 10.
COPY --from=net8 /usr/share/dotnet/shared/ /usr/share/dotnet/shared/

ENV DEBIAN_FRONTEND=noninteractive \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_NOLOGO=1 \
    GIT_TERMINAL_PROMPT=0

# Native dependencies for Uno's Linux desktop renderer and WebView, plus a virtual display.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 build-essential \
      dbus-x11 fonts-dejavu-core libfontconfig1 libgl1 libegl1 \
      libx11-6 libxrandr2 libxi6 libice6 libsm6 libgtk-3-0t64 \
      libwebkit2gtk-4.1-0 xvfb xauth \
    && rm -rf /var/lib/apt/lists/*

# Scanner contract: retain the sources, Git history, build outputs and NuGet cache in the image.
COPY . /src
WORKDIR /src

# The scanner clones only the top-level repository. Fetch the exact pinned submodule commits here,
# while the build still has network access, including the nested crypto and Proton libraries.
RUN git -c credential.helper= submodule update --init --recursive

# Build TuviCore and its test projects, including mail, encrypted storage, backup and key management.
RUN dotnet build gitmodules/TuviCore/Sources/Tuvi.Core.slnx \
      --configuration Release --verbosity minimal \
      -p:DebugType=portable -p:DebugSymbols=true

# Restrict Uno to Linux desktop so restore does not require Android, iOS or Windows workloads.
RUN dotnet build src/Eppie.App/Eppie.App/Eppie.App.csproj \
      --configuration Release --framework net10.0-desktop --verbosity minimal \
      -p:OverrideTargetFrameworks=net10.0-desktop \
      -p:DebugType=portable -p:DebugSymbols=true

RUN dotnet build src/Eppie.App/Tests/Eppie.App.ViewModels.Tests/Eppie.App.ViewModels.Tests.csproj \
      --configuration Release --verbosity minimal \
      -p:DebugType=portable -p:DebugSymbols=true
