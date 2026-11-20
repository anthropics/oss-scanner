FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1

# Ubuntu's SDK packages supply the 10.0.1xx SDK required by global.json,
# together with .NET 8 for the project's other supported test framework.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 bash \
      dotnet-sdk-10.0 dotnet-sdk-8.0 \
      build-essential clang zlib1g-dev libfontconfig1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Keep restored packages, built test drivers, and the checked-in fixture corpus
# in the image: the scanner runs without network access after this build.
RUN dotnet restore OfficeIMO.sln --disable-parallel \
    && dotnet build OfficeIMO.sln --configuration Release --no-restore --maxcpucount:2

RUN dotnet test OfficeIMO.Security.Tests/OfficeIMO.Security.Tests.csproj \
      --configuration Release --framework net10.0 --no-build --no-restore \
      --filter 'Category!=Performance' \
      --logger 'console;verbosity=minimal'
