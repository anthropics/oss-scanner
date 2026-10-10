# Builds IW4MAdmin (develop) the way the project's CI does (.github/workflows/build_application.yml), minus the
# release-packaging steps. The project targets net10.0.
FROM mcr.microsoft.com/dotnet/sdk:10.0
ENV DEBIAN_FRONTEND=noninteractive \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 curl \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Restore every project while network access is available, so later builds work offline.
RUN dotnet restore Application/Application.csproj \
    && find Plugins -name '*.csproj' -print0 | xargs -0 -n1 dotnet restore

# Prerelease is the configuration CI ships; Debug runs a Windows-only PowerShell pre-build step. Keep full symbols.
ENV BUILD_ARGS="-c Prerelease --no-restore -p:Platform=x64 -p:DebugType=portable -p:DebugSymbols=true"

# Build the core application (pulls in SharedLibraryCore, Data, WebCommon, WebfrontCore, Integrations).
RUN dotnet build Application/Application.csproj $BUILD_ARGS

# Build each plugin. A failing plugin should not hide the rest of the build from the scanner.
RUN for p in $(find Plugins -name '*.csproj'); do \
      dotnet build "$p" $BUILD_ARGS || echo "WARNING: failed to build $p"; \
    done

# Lay out a runnable copy at /src/Publish the way CI's release does (the app expects <root>/Lib/IW4MAdmin.dll and
# resolves Configuration/ and Plugins/ from <root>), so findings can be reproduced against a running instance:
#   cd /src/Publish && dotnet Lib/IW4MAdmin.dll
# Webfront CSS/JS bundling is skipped. A failure here leaves the build above intact.
RUN (for p in $(find Plugins -name '*.csproj'); do \
       dotnet publish "$p" $BUILD_ARGS -o BUILD/Plugins -p:DeployOnBuild=false || echo "WARNING: failed to publish $p"; \
     done \
     && dotnet publish Application/Application.csproj $BUILD_ARGS -o Publish \
     && bash Application/BuildScripts/PostBuild.sh /src/Publish /src \
     && cp BUILD/Plugins/*.dll Publish/Plugins/ \
     && (cp Plugins/ScriptPlugins/*.cs Plugins/ScriptPlugins/*.js Publish/Plugins/ 2>/dev/null || true)) \
    || echo "WARNING: could not lay out /src/Publish"

# The app refuses to start without localization files; CI downloads them at build time.
RUN mkdir -p Publish/Localization \
    && for l in en-US ru-RU es-EC pt-BR de-DE; do \
         curl -fsS "https://master.iw4.zip/localization/$l" -o "Publish/Localization/IW4MAdmin.$l.json" \
           || echo "WARNING: could not download $l localization"; \
       done
