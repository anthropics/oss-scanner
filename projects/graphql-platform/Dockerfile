# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/runtime-deps:11.0

ENV DOTNET_ROOT=/usr/share/dotnet \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE=1 \
    DOTNET_GENERATE_ASPNET_CERTIFICATE=false \
    NUGET_XMLDOC_MODE=skip \
    MSBUILDDISABLENODEREUSE=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends ca-certificates curl git \
    && rm --recursive --force /var/lib/apt/lists/*

# The SDK that global.json pins, which includes the net11.0 runtimes.
COPY global.json /opt/graphql-platform/global.json
RUN curl \
        --fail \
        --silent \
        --show-error \
        --location \
        --output /tmp/dotnet-install.sh \
        https://dot.net/v1/dotnet-install.sh \
    && bash /tmp/dotnet-install.sh \
        --jsonfile /opt/graphql-platform/global.json \
        --install-dir /usr/share/dotnet \
    && ln --symbolic /usr/share/dotnet/dotnet /usr/local/bin/dotnet \
    && rm /tmp/dotnet-install.sh

COPY . /src
WORKDIR /src

# The test projects CI runs (every *.Tests.csproj in src/All.slnx, the selection that
# .github/actions/generate-test-matrix makes), an MSBuild project that builds them for
# net11.0, and the graphql-platform-test script that runs them.
RUN <<'SETUP'
set -o errexit -o nounset
grep --only-matching --extended-regexp 'Path="[^"]+\.Tests\.csproj"' src/All.slnx \
    | sed --regexp-extended 's#^Path="#src/#; s#"$##' \
    > /opt/graphql-platform/test-projects.txt
test -s /opt/graphql-platform/test-projects.txt

cat > /opt/graphql-platform/build.proj <<'PROJECT'
<Project>
  <Target Name="Build">
    <ReadLinesFromFile File="$(MSBuildThisFileDirectory)test-projects.txt">
      <Output TaskParameter="Lines" ItemName="TestProject" />
    </ReadLinesFromFile>
    <MSBuild
      Projects="@(TestProject->'/src/%(Identity)')"
      Targets="Build"
      Properties="TargetFramework=net11.0"
      BuildInParallel="true" />
  </Target>
</Project>
PROJECT

cat > /usr/local/bin/graphql-platform-test <<'SCRIPT'
#!/usr/bin/env bash
# Runs the prebuilt test projects for net11.0, or only the projects given as arguments.
set -o nounset -o pipefail
cd /src
results="${GRAPHQL_PLATFORM_TEST_RESULTS:-/tmp/graphql-platform-test-results}"
mkdir --parents "$results"
if [ "$#" -eq 0 ]; then
    mapfile -t projects < /opt/graphql-platform/test-projects.txt
else
    projects=("$@")
fi
status=0
for project in "${projects[@]}"; do
    name="$(basename "$project" .csproj)"
    if ! timeout 900 dotnet test \
            --project "$project" \
            --framework net11.0 \
            --no-build \
            --results-directory "$results/$name"; then
        status=1
    fi
done
exit "$status"
SCRIPT
chmod +x /usr/local/bin/graphql-platform-test
SETUP

# Restores every project in src/All.slnx for every target framework, then builds the test
# projects for net11.0, the target framework CI builds and tests.
RUN cd /src \
    && dotnet restore src/All.slnx \
    && dotnet msbuild /opt/graphql-platform/build.proj -maxCpuCount -verbosity:minimal \
    && dotnet build-server shutdown

# Runs one fast suite. A failure is logged as a warning and does not fail the build.
RUN cd /src \
    && (timeout 600 graphql-platform-test \
            src/HotChocolate/Language/test/Language.Tests/HotChocolate.Language.Tests.csproj \
        || echo "WARNING: HotChocolate.Language.Tests reported failures") \
    && rm --recursive --force /tmp/graphql-platform-test-results

CMD ["bash"]
