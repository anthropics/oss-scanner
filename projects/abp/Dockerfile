# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/dotnet/sdk:10.0

ENV DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_FIRST_TIME_EXPERIENCE=1 \
    DOTNET_CLI_WORKLOAD_UPDATE_NOTIFY_DISABLE=true \
    NUGET_XMLDOC_MODE=skip \
    MSBUILDDISABLENODEREUSE=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash ca-certificates curl git python3 sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN <<'SETUP'
set -eu
mkdir -p /opt/abp-oss-scanner
cat > /opt/abp-oss-scanner/test-projects.txt <<'PROJECTS'
framework/test/Volo.Abp.Security.Tests/Volo.Abp.Security.Tests.csproj
framework/test/Volo.Abp.Authorization.Tests/Volo.Abp.Authorization.Tests.csproj
framework/test/Volo.Abp.MultiTenancy.Tests/Volo.Abp.MultiTenancy.Tests.csproj
framework/test/Volo.Abp.AspNetCore.MultiTenancy.Tests/Volo.Abp.AspNetCore.MultiTenancy.Tests.csproj
framework/test/Volo.Abp.AspNetCore.Tests/Volo.Abp.AspNetCore.Tests.csproj
framework/test/Volo.Abp.AspNetCore.Mvc.Tests/Volo.Abp.AspNetCore.Mvc.Tests.csproj
framework/test/Volo.Abp.EntityFrameworkCore.Tests/Volo.Abp.EntityFrameworkCore.Tests.csproj
framework/test/Volo.Abp.MongoDB.Tests/Volo.Abp.MongoDB.Tests.csproj
modules/identity/test/Volo.Abp.Identity.EntityFrameworkCore.Tests/Volo.Abp.Identity.EntityFrameworkCore.Tests.csproj
modules/identity/test/Volo.Abp.Identity.MongoDB.Tests/Volo.Abp.Identity.MongoDB.Tests.csproj
modules/identity/test/Volo.Abp.Identity.AspNetCore.Tests/Volo.Abp.Identity.AspNetCore.Tests.csproj
modules/account/test/Volo.Abp.Account.Application.Tests/Volo.Abp.Account.Application.Tests.csproj
modules/permission-management/test/Volo.Abp.PermissionManagement.EntityFrameworkCore.Tests/Volo.Abp.PermissionManagement.EntityFrameworkCore.Tests.csproj
modules/permission-management/test/Volo.Abp.PermissionManagement.MongoDB.Tests/Volo.Abp.PermissionManagement.MongoDB.Tests.csproj
modules/openiddict/test/Volo.Abp.OpenIddict.EntityFrameworkCore.Tests/Volo.Abp.OpenIddict.EntityFrameworkCore.Tests.csproj
modules/openiddict/test/Volo.Abp.OpenIddict.MongoDB.Tests/Volo.Abp.OpenIddict.MongoDB.Tests.csproj
modules/openiddict/test/Volo.Abp.OpenIddict.AspNetCore.Tests/Volo.Abp.OpenIddict.AspNetCore.Tests.csproj
modules/tenant-management/test/Volo.Abp.TenantManagement.EntityFrameworkCore.Tests/Volo.Abp.TenantManagement.EntityFrameworkCore.Tests.csproj
modules/tenant-management/test/Volo.Abp.TenantManagement.MongoDB.Tests/Volo.Abp.TenantManagement.MongoDB.Tests.csproj
PROJECTS
cat > /opt/abp-oss-scanner/source-projects.txt <<'PROJECTS'
framework/test/Volo.Abp.AspNetCore.Mvc.PlugIn/Volo.Abp.AspNetCore.Mvc.PlugIn.csproj
modules/account/src/Volo.Abp.Account.Web/Volo.Abp.Account.Web.csproj
modules/account/src/Volo.Abp.Account.HttpApi/Volo.Abp.Account.HttpApi.csproj
modules/identity/src/Volo.Abp.Identity.HttpApi/Volo.Abp.Identity.HttpApi.csproj
modules/permission-management/src/Volo.Abp.PermissionManagement.HttpApi/Volo.Abp.PermissionManagement.HttpApi.csproj
PROJECTS
cat > /usr/local/bin/abp-oss-build <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
cd /src
while IFS= read -r project; do
    dotnet restore "$project" -p:NuGetAudit=false --verbosity minimal
    dotnet build "$project" --no-restore --configuration Debug \
        --disable-build-servers --verbosity quiet -m:2
 done < <(cat /opt/abp-oss-scanner/test-projects.txt /opt/abp-oss-scanner/source-projects.txt)
SCRIPT
cat > /usr/local/bin/abp-oss-test <<'SCRIPT'
#!/usr/bin/env bash
set -euo pipefail
cd /src
results="${1:-/tmp/abp-oss-results}"
mkdir -p "$results"
status=0
while IFS= read -r project; do
    name="$(basename "$project" .csproj)"
    if ! timeout 300 dotnet test "$project" --no-build --no-restore \
        --configuration Debug --logger "trx;LogFileName=${name}.trx" \
        --results-directory "$results" --verbosity minimal; then
        status=1
    fi
 done < /opt/abp-oss-scanner/test-projects.txt
dotnet build-server shutdown
exit "$status"
SCRIPT
chmod +x /usr/local/bin/abp-oss-build /usr/local/bin/abp-oss-test
SETUP

RUN abp-oss-build && dotnet build-server shutdown

CMD ["bash"]
