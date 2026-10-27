# Linux audit environment for the Anthropic OSS Scanner. Clean PUBLIC checkout only.
# Full source scope, including platforms that Linux cannot execute.
FROM --platform=linux/amd64 oven/bun:1.4.4@sha256:1d22548f177f4ff38e0c15baa3c2c46c6c2060ba2d1bc573bb4720b407548f1d AS bun
FROM --platform=linux/amd64 rust:1-bookworm@sha256:48b7f435b8fc6378ce43b44f15e3a47fd8919b2825f835c39bd4bd3da50af5b8 AS rust
FROM --platform=linux/amd64 node:24-bookworm@sha256:6449e19d8184d84062525b6a7524def03146c2cb04a7f08b076680d0e8e4240a AS node
FROM --platform=linux/amd64 python:3.13-bookworm@sha256:a3799099b64fd333f262768c7a64733f6e4edb7bc569813710a100214bdcf278 AS audit-env
COPY --from=node /usr/local /usr/local
COPY --from=bun /usr/local/bin/bun /usr/local/bin/bun
COPY --from=rust /usr/local/cargo /usr/local/cargo
COPY --from=rust /usr/local/rustup /usr/local/rustup
ENV CARGO_HOME=/usr/local/cargo RUSTUP_HOME=/usr/local/rustup \
    PUB_CACHE=/opt/pub-cache FLUTTER_ROOT=/opt/flutter \
    PATH=/opt/flutter/bin:/usr/local/cargo/bin:$PATH \
    CI=true NEXT_TELEMETRY_DISABLED=1 TURBO_TELEMETRY_DISABLED=1 \
    WRANGLER_SEND_METRICS=false
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl git python3 build-essential clang cmake ninja-build \
    pkg-config xz-utils unzip time libssl-dev libgtk-3-dev libwebkit2gtk-4.1-dev \
    libsoup-3.0-dev libsecret-1-dev libasound2-dev libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev postgresql-client \
    && rm -rf /var/lib/apt/lists/*
# Flutter 3.47.8 has an official Linux x64 archive only. This image targets amd64.
RUN python3 - <<'FETCH_FLUTTER'
import hashlib,json,os,tarfile,urllib.request
url='https://storage.googleapis.com/flutter_infra_release/releases/stable/linux/flutter_linux_3.47.8-stable.tar.xz'
sha256='baf7dcc5a3dbba60fe863bf493a6cf203195621f7786eaa5a1bba02cd0d87dd2'
path='/tmp/flutter.tar.xz'
hash=hashlib.sha256()
with urllib.request.urlopen(url) as source, open(path,'wb') as target:
 while chunk:=source.read(1024*1024):
  hash.update(chunk)
  target.write(chunk)
assert hash.hexdigest()==sha256, 'Flutter archive checksum mismatch'
open('/opt/flutter-release.json','w').write(json.dumps({'version':'3.47.8','arch':'x64','url':url,'sha256':sha256},indent=2))
with tarfile.open(path) as archive: archive.extractall('/opt',filter='data')
os.remove(path)
FETCH_FLUTTER
RUN git config --global --add safe.directory /opt/flutter \
    && flutter config --no-analytics --enable-linux-desktop \
    && flutter precache --linux
# Scanner contract: retain the ENTIRE public checkout, not a pruned web workspace.
COPY . /src
WORKDIR /src
# An anonymous public checkout is required; reject unexpected local configuration.
# The security contact maintains this allowlist when tracked npm configuration changes.
RUN python3 - <<'CHECK_CONTEXT'
from pathlib import Path
import hashlib
root=Path('/src')
public_npmrc={
 '.npmrc':'45297ffed5aa720d67bbf1eb033d9e1409cdbff1d4c55c26adf69817fa019404',
 'apps/nova/.npmrc':'c320068635cb4192cdae9d8d551b328299349d37f2530432a38d6b2891e5c15d',
 'apps/rewise/.npmrc':'c320068635cb4192cdae9d8d551b328299349d37f2530432a38d6b2891e5c15d',
 'apps/web/.npmrc':'1f5c8d3167e538a20fb98bd382c5b976af99e1f60afda51293af679147eb8ca0',
 'packages/ai/.npmrc':'c320068635cb4192cdae9d8d551b328299349d37f2530432a38d6b2891e5c15d',
}
for p in root.rglob('*'):
 if not p.is_file():continue
 rel=p.relative_to(root).as_posix()
 if p.name=='.npmrc':
  assert public_npmrc.get(rel)==hashlib.sha256(p.read_bytes()).hexdigest(), 'Unreviewed npm config: '+rel
 elif (p.name in ('.env','.netrc') or p.name.startswith('.env.')) and not p.name.endswith(('.example','.sample','.template')):
  raise RuntimeError('Unexpected local configuration: '+rel)
CHECK_CONTEXT
RUN bun install --frozen-lockfile
# apps/backend is a paused runtime, excluded from build/test like CI. Fetch its
# crates only so dependency sources can be read offline.
RUN cargo fetch --locked --manifest-path apps/backend/Cargo.toml
RUN cd apps/mobile && flutter pub get --enforce-lockfile && flutter gen-l10n
# flutter_edge_ai_litertlm's build hook fetches native libs from GitHub releases
# (not pub.dev) and verifies its own pinned sha256. Run the hook once while the
# build has network so offline tests reuse $HOME/.cache/flutter_gemma/native.
RUN cd apps/mobile && flutter test --no-pub test/counter \
    && find /root/.cache/flutter_gemma/native -name '*.so' | grep -q .
# The same workspace setup build CI runs before unit tests (turbo-unit-tests.yaml).
RUN bun run turbo:local run build --concurrency=1 --filter=@tuturuuu/types \
    --filter=@tuturuuu/supabase --filter=@tuturuuu/masonry \
    --filter=@tuturuuu/internal-api --filter=tuturuuu
CMD ["/bin/bash"]
