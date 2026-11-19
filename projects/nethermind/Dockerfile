FROM mcr.microsoft.com/dotnet/sdk:10.0.400-resolute@sha256:8caacec8e070ea6ab07b1d9c2b6bf397fca92ab4de0e52bbf25d381409782158

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates git python3 build-essential cmake pkg-config libsnappy-dev \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN dotnet restore src/Nethermind/Nethermind.slnx --locked-mode \
    && dotnet build src/Nethermind/Nethermind.slnx -c Release --no-restore
