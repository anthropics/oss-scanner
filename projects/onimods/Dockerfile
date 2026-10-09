FROM rust:1.96-trixie
COPY --from=mcr.microsoft.com/dotnet/sdk:10.0 /usr/share/dotnet /usr/share/dotnet
ENV PATH="/usr/share/dotnet:$PATH" DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_NOLOGO=1
ENV CARGO_BUILD_JOBS=2 \
    RUSTFLAGS="-C debuginfo=1 -C force-frame-pointers=yes"
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git pkg-config libssl-dev cmake clang libclang-dev \
      protobuf-compiler libfuse3-dev python3 unzip zip jq \
    && rm -rf /var/lib/apt/lists/*
COPY . /src
WORKDIR /src
RUN apt-get update && apt-get install -y --no-install-recommends libicu76 libkrb5-3 \
    && rm -rf /var/lib/apt/lists/*
RUN cargo fetch --locked && cargo build --locked && cargo test --locked --no-run
RUN set -e; for project in tests/*/*.csproj; do dotnet build "$project" --nologo; done
