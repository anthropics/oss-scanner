# syntax=docker/dockerfile:1
# Scanner contract: the checkout is the build context; COPY it to /src, fetch every dependency here (network is
# available only during this build), and leave sources, build outputs and NuGet cache in the image.
FROM mcr.microsoft.com/dotnet/sdk:11.0

# ILSpy, ilspycmd, TestPlugin and ILSpy.ReadyToRun target net10.0; the test projects target net11.0 (see AGENTS.md).
COPY --from=mcr.microsoft.com/dotnet/runtime:10.0 /usr/share/dotnet/shared/ /usr/share/dotnet/shared/

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_CLI_USE_MSBUILD_SERVER=false \
    DOTNET_gcServer=0 \
    GIT_TERMINAL_PROMPT=0

# libfontconfig1: SkiaSharp, which the headless Avalonia UI tests (ILSpy.Tests) initialise.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 bash libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# The scanner clones only the top-level repository. ICSharpCode.Decompiler.Tests needs the ILSpy-tests submodule
# (reference assemblies for TargetNet40 configs, and the ILSpy-tests/nuget package cache it insists on).
RUN git -c credential.helper= submodule update --init --recursive

# Same restore/build as the Linux CI job (build-ilspy.yml "Desktop"): the cross-platform UI, the decompiler
# libraries, ilspycmd and their tests. Package pruning off keeps packages.lock.json whole (RestoreLockedMode).
RUN dotnet restore ILSpy.Desktop.slnf -p:RestoreEnablePackagePruning=false \
 && dotnet build ILSpy.Desktop.slnf --no-restore -c Debug -m \
 && dotnet build-server shutdown

# First run of the decompiler suite downloads Roslyn toolsets, vswhere and reference packs from NuGet and publishes
# the self-contained test runner (Tester.Initialize). Do it now, while online, so the suite runs offline later.
# One tiny test is enough to trigger the [SetUpFixture]; a failure here must not sink the image.
RUN dotnet test --project ICSharpCode.Decompiler.Tests/ICSharpCode.Decompiler.Tests.csproj --no-build -c Debug \
      --filter "FullyQualifiedName~PrettyTestRunner.AllFilesHaveTests" \
    || echo "WARNING: decompiler test warm-up reported failures"
RUN dotnet build-server shutdown

CMD ["bash"]
