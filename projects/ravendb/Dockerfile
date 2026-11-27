# syntax=docker/dockerfile:1
# Build RavenDB for Anthropic's OSS Scanner.
# Scanner contract: the checkout is the build context and lives at /src. Network is available only during this
# build, so the .NET SDK, NuGet packages, the embeddings model and Studio's npm packages are all fetched here.
# The scanner removes the repository's root .dockerignore (written for release images, it excludes test/, bench/ and
# src/Raven.Pal) before building a Dockerfile kept beside project.yaml, so the whole source tree is in the context.
FROM debian:bookworm

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive \
    DOTNET_ROOT=/usr/share/dotnet \
    PATH=/usr/share/dotnet:$PATH \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_CLI_USE_MSBUILD_SERVER=false \
    GIT_TERMINAL_PROMPT=0

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl \
      libicu72 libssl3 zlib1g libstdc++6 libgcc-s1 tzdata \
    && rm -rf /var/lib/apt/lists/*

# Node.js for Studio, the version src/Raven.Studio/.nvmrc pins.
COPY --from=node:24-bookworm-slim /usr/local/bin/node /usr/local/bin/node
COPY --from=node:24-bookworm-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && node --version && npm --version

COPY . /src
WORKDIR /src

# The .NET SDK exactly as pinned by the branch's global.json (the stock sdk images may carry an older feature band).
RUN curl -fsSL https://dot.net/v1/dotnet-install.sh -o /tmp/dotnet-install.sh \
    && bash /tmp/dotnet-install.sh --jsonfile /src/global.json --install-dir /usr/share/dotnet \
    && rm /tmp/dotnet-install.sh \
    && dotnet --info

# Server, client, Voron, Corax, Sparrow, tools and all test projects. Debug keeps the extra assertions that Release
# strips out (see AGENTS.md). The build also downloads the local embeddings model (src/DownloadEmbeddings.targets).
RUN dotnet restore RavenDB.sln \
    && dotnet build RavenDB.sln --no-restore -c Debug \
    && dotnet build-server shutdown

# Studio (served by the server at /studio). A Studio failure must not sink the image: the server and tests still work.
# Same steps as `npm run restore_compile`, but the typings come from the Debug build above: scripts/typings.js would
# rebuild the whole server in Release and cost the build time limit. Type checking is skipped, it produces nothing.
RUN cd src/Raven.Studio \
    && (npm ci \
        && npm run fix-packages \
        && npm run generate-icons-font \
        && dotnet run -c Debug --no-build --project ../../tools/TypingsGenerator/TypingsGenerator.csproj \
        && npm run compile \
        || echo "WARNING: Studio build failed")

# Warm-up without network, like the scan: one test that starts an in-process server and stores a document.
RUN --network=none dotnet test test/FastTests/FastTests.csproj --no-build -c Debug \
      --filter "FullyQualifiedName=FastTests.Client.Update.Update_Document" \
    || echo "WARNING: offline warm-up test failed"

CMD ["bash"]
