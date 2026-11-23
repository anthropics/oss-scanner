# syntax=docker/dockerfile:1
# ClickHouse for the OSS Scanner.
#
# A full build of ClickHouse takes hours on 16 CPUs, far beyond the 45-minute budget, so this image does not compile it.
# Instead it takes the binaries that ClickHouse CI built for the scanned commit (or, if CI has not finished with it yet,
# for its nearest first-parent ancestor on master that has them):
#   /opt/clickhouse/release/clickhouse     the release build, as shipped to users
#   /opt/clickhouse/asan/clickhouse        AddressSanitizer + UndefinedBehaviorSanitizer, to confirm memory-safety findings
#   /opt/clickhouse/COMMIT                 the commit those binaries were built from; compare with `git -C /src rev-parse HEAD`
# `clickhouse` on PATH is the release build.
#
# The image is kept small, because the history of the repository alone is about 16 GB and the build machine keeps
# several copies of it: the submodules (contrib/) are not checked out, and the binaries are stripped of debug info
# (from 13 GB to 3 GB; stack traces keep function names, but not file names and lines).
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUTF8=1

# llvm-18 for llvm-strip, and for llvm-symbolizer, which turns sanitizer reports into stack traces.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git python3 python3-jinja2 python3-termcolor llvm-18 \
      gdb file less procps psmisc netcat-openbsd zstd xz-utils \
    && rm -rf /var/lib/apt/lists/*

ENV LLVM_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18 \
    ASAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18 \
    UBSAN_SYMBOLIZER_PATH=/usr/bin/llvm-symbolizer-18 \
    UBSAN_OPTIONS=print_stacktrace=1

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN git config --global --add safe.directory '*'

# Find the CI binaries for the scanned commit. Each master commit has a report, result_masterci.json, whose build jobs
# either built the binary (status OK, the link points at it) or reused it from an earlier run with the same sources
# (status SKIPPED, the link points at the report of that run, possibly a merge queue run). Walk the first-parent history
# from HEAD to the first commit for which both binaries exist. Each binary is self-extracting: it is unpacked by its
# first run and stripped in the same step, so the image does not keep the compressed or the unstripped copy.
RUN <<'EOF' python3 -I -
import json, os, re, subprocess, sys, urllib.error, urllib.parse, urllib.request

REPORTS = "https://s3.amazonaws.com/clickhouse-test-reports"
ARCH = {"amd64": "amd", "arm64": "arm"}[subprocess.check_output(["dpkg", "--print-architecture"], text=True).strip()]
BUILDS = {"release": "release", "asan": "asan_ubsan"}


def normalize(name):
    return re.sub(r"[ (){}'\[\],/\-:\"&]", "_", name.lower())


def fetch_json(url):
    try:
        with urllib.request.urlopen(url, timeout=60) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):  # S3 answers 403 for a key that does not exist
            return None
        raise


def report(ref, sha, workflow):
    return fetch_json(f"{REPORTS}/REFs/{ref}/{sha}/{normalize(workflow)}/result_{normalize(workflow)}.json")


def artifact(result, job, depth=0):
    """The URL of the `clickhouse` binary that `job` in the workflow report `result` built or reused, or None."""
    for entry in result.get("results", []):
        if entry["name"] != job:
            continue
        links = entry.get("links") or []
        if entry["status"] == "OK":
            return next((link for link in links if link.endswith("/clickhouse")), None)
        if entry["status"] == "SKIPPED" and links and "praktika.html" in links[0] and depth < 3:
            query = urllib.parse.parse_qs(urllib.parse.urlparse(links[0]).query)
            if "REF" not in query:
                return None
            producer = report(query["REF"][0], query["sha"][0], query["name_0"][0])
            return producer and artifact(producer, job, depth + 1)
        return None
    return None


def exists(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60):
            return True
    except urllib.error.HTTPError as error:
        if error.code in (403, 404):
            return False
        raise


head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
for sha in subprocess.check_output(["git", "rev-list", "--first-parent", "-n", "300", "HEAD"], text=True).split():
    result = report("master", sha, "MasterCI")
    if not result:
        continue
    urls = {kind: artifact(result, f"Build ({ARCH}_{build})") for kind, build in BUILDS.items()}
    if all(urls.values()) and all(exists(url) for url in urls.values()):
        break
else:
    sys.exit(f"no first-parent ancestor of {head} among the last 300 has CI binaries for {ARCH}")

for kind, url in urls.items():
    os.makedirs(f"/opt/clickhouse/{kind}", exist_ok=True)
    print(f"{kind}: {url}", flush=True)
    path = f"/opt/clickhouse/{kind}/clickhouse"
    subprocess.run(["curl", "-fsS", "--retry", "5", "-o", path, url], check=True)
    os.chmod(path, 0o755)
    subprocess.run([path, "--version"], check=True)
    subprocess.run(["llvm-strip-18", "--strip-debug", path], check=True)
with open("/opt/clickhouse/COMMIT", "w") as file:
    file.write(sha + "\n")
behind = subprocess.check_output(["git", "rev-list", "--count", f"{sha}..{head}"], text=True).strip()
print(f"binaries are from {sha}; HEAD {head} is {behind} commits ahead of it")
EOF

# The tool names (clickhouse-client, clickhouse-local, ...) are symlinks to the release build.
RUN for kind in release asan; do /opt/clickhouse/$kind/clickhouse local --query "SELECT version()"; done \
    && ln -s /opt/clickhouse/release/clickhouse /usr/local/bin/clickhouse \
    && for tool in client local server keeper benchmark compressor format obfuscator disks; do \
         ln -s /opt/clickhouse/release/clickhouse /usr/local/bin/clickhouse-$tool; done \
    && ln -s /opt/clickhouse/asan/clickhouse /usr/local/bin/clickhouse-asan

# Show in the build log that a server starts and answers offline. The server runs in a session of its own, because
# `SYSTEM SHUTDOWN` sends SIGTERM to the whole process group of the server, which would end this build step.
RUN <<'EOF' bash
set -euo pipefail
mkdir -p /tmp/smoke && cd /tmp/smoke
setsid clickhouse server > server.log 2>&1 &
server=$!
for i in $(seq 120); do clickhouse client --query "SELECT 1" > /dev/null 2>&1 && break; sleep 1; done
clickhouse client --query "SELECT version(), (SELECT value FROM system.build_options WHERE name = 'GIT_HASH')"
clickhouse client --query "CREATE TABLE t (x UInt64) ENGINE = MergeTree ORDER BY x"
clickhouse client --query "INSERT INTO t SELECT number FROM numbers(1000000)"
test "$(clickhouse client --query "SELECT sum(x) FROM t")" = 499999500000
kill "$server"
wait "$server"
cd / && rm -rf /tmp/smoke
EOF
