# syntax=docker/dockerfile:1
# A current userspace for the scanner's tools, with Node for the FE UI.
FROM node:22-bookworm-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d AS source_build

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        autoconf automake bash binutils-dev bison byacc bzip2 ca-certificates \
        curl file flex g++ gettext git gperf help2man krb5-user libaio1 \
        libcurl4-openssl-dev libffi-dev libiberty-dev libkrb5-dev libncurses5 \
        libncurses-dev libssl-dev libtool libtool-bin libxml2-dev make \
        mariadb-client nasm openjdk-17-jdk-headless patch pkg-config procps \
        python-is-python3 python3 python3-pip \
        python3-venv texinfo unzip util-linux wget xz-utils zip zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# branch-4.2's docker/compilation/Dockerfile selects LDB 0.25. Install the
# compiler directly instead of pulling a 2 GB image of master dependencies.
RUN curl -fL --retry 3 https://github.com/amosbird/ldb_toolchain_gen/releases/download/v0.25/ldb_toolchain_gen.sh \
        -o /tmp/ldb_toolchain_gen.sh \
    && echo '09d4a300a5d55302582f8291a7309474627ecdec3648ee9f9c912244b2d4472e  /tmp/ldb_toolchain_gen.sh' | sha256sum -c -
RUN bash /tmp/ldb_toolchain_gen.sh /var/local/ldb-toolchain \
    && rm /tmp/ldb_toolchain_gen.sh

RUN curl -fL --retry 3 https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.9/apache-maven-3.9.9-bin.tar.gz \
        -o /tmp/maven.tar.gz \
    && mkdir -p /opt/maven \
    && tar -xzf /tmp/maven.tar.gz -C /opt/maven --strip-components=1 \
    && rm /tmp/maven.tar.gz

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    MAVEN_HOME=/opt/maven \
    DORIS_THIRDPARTY=/src/thirdparty \
    DORIS_HOME=/src \
    CARGO_HOME=/opt/cargo \
    RUSTUP_HOME=/opt/rustup \
    REPOSITORY_URL=https://doris-thirdparty-repo.bj.bcebos.com/thirdparty \
    BUILD_TYPE=ASAN \
    USE_AVX2=0 \
    STRIP_DEBUG_INFO=OFF \
    CCACHE_DISABLE=1 \
    FE_MAVEN_THREADS=4 \
    FE_UT_PARALLEL=1 \
    MAVEN_OPTS="-Xmx4g"
ENV PATH="/opt/cargo/bin:/opt/maven/bin:/usr/lib/jvm/java-17-openjdk-amd64/bin:/var/local/ldb-toolchain/bin:/src/thirdparty/installed/bin:${PATH}"

# The enrolled branch requires the same Rust compiler for Lance and Paimon.
RUN curl -fsSL --retry 3 https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && sh /tmp/rustup-init.sh -y --no-modify-path --profile minimal --default-toolchain 1.94.0 \
    && rm /tmp/rustup-init.sh

# XZ's autogen.sh requires Debian's separate autopoint package. Keep this
# addition after the toolchain setup so existing compiler layers remain reusable.
RUN apt-get update \
    && apt-get install -y --no-install-recommends autopoint \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

# Cache dependencies separately from the application sources. Use Doris' own
# archive mirror, with upstream URL fallbacks and the branch's checksum checks;
# this also avoids the unreliable Apache archive download seen for ORC 1.9.0.
COPY env.sh /src/env.sh
COPY thirdparty /src/thirdparty
ARG BUILD_JOBS
# Preserve downloads across retries. When the dependency definitions change,
# unpack and patch fresh sources instead of reusing a previous patched tree.
# Try TimSort's raw URL first; unauthenticated API requests can be rate limited
# on shared runners. Keep the contents API as a fallback for the raw host.
# download-thirdparty.sh verifies the enrolled branch's checksum either way.
RUN --mount=type=cache,id=oss-scanner-doris-4.2-src,target=/src/thirdparty/src,sharing=locked \
    find /src/thirdparty/src -mindepth 1 -maxdepth 1 -type d -exec rm -rf {} + \
    && (curl -fL --retry 3 --connect-timeout 15 --max-time 60 \
        'https://raw.githubusercontent.com/timsort/cpp-TimSort/3.x.y/include/gfx/timsort.hpp' \
        -o /src/thirdparty/src/timsort.hpp \
    || curl -fL --retry 3 --connect-timeout 15 --max-time 60 -H 'Accept: application/vnd.github.raw+json' \
        'https://api.github.com/repos/timsort/cpp-TimSort/contents/include/gfx/timsort.hpp?ref=3.x.y' \
        -o /src/thirdparty/src/timsort.hpp) \
    && bash ./thirdparty/download-thirdparty.sh

# Checkpoint the dependency batches so a later failure does not discard every
# compiled library. Follow the branch's upstream order; the last call builds
# the remainder of its default package list, starting at js_and_css.
RUN --mount=type=cache,id=oss-scanner-doris-4.2-src,target=/src/thirdparty/src,sharing=locked \
    build_jobs="${BUILD_JOBS:-$(nproc)}" \
    && CARGO_BUILD_JOBS="${build_jobs}" bash ./thirdparty/build-thirdparty.sh -j "${build_jobs}" \
        jindofs juicefs odbc openssl libevent zlib crc32c lz4 bzip lzo2 zstd \
        boost abseil gflags gtest glog protobuf rapidjson
RUN --mount=type=cache,id=oss-scanner-doris-4.2-src,target=/src/thirdparty/src,sharing=locked \
    build_jobs="${BUILD_JOBS:-$(nproc)}" \
    && CARGO_BUILD_JOBS="${build_jobs}" bash ./thirdparty/build-thirdparty.sh -j "${build_jobs}" \
        snappy gperftools curl re2 hyperscan thrift leveldb brpc lzma libunwind \
        jemalloc_doris rocksdb krb5 cyrus_sasl librdkafka flatbuffers orc cares

# Hadoop's CMake FindJNI also requires AWT, which the headless JDK omits.
RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jdk \
    && rm -rf /var/lib/apt/lists/*

# Allow later batches to use more workers without invalidating earlier batches.
ARG NATIVE_BUILD_JOBS
RUN --mount=type=cache,id=oss-scanner-doris-4.2-src,target=/src/thirdparty/src,sharing=locked \
    build_jobs="${NATIVE_BUILD_JOBS:-${BUILD_JOBS:-$(nproc)}}" \
    && CARGO_BUILD_JOBS="${build_jobs}" bash ./thirdparty/build-thirdparty.sh -j "${build_jobs}" \
        grpc arrow lance_c s2 bitshuffle croaringbitmap fmt parallel_hashmap \
        pdqsort timsort libdivide cctz tsan_header mysql aws_sdk

# Run Hadoop's Maven reactor in parallel. Older plugins can exhaust the resolver
# lock timeout during downloads; retry only that failed Maven command serially.
RUN mkdir -p /opt/hadoop-maven-bin \
    && printf '%s\n' \
        '#!/bin/bash' \
        'set -o pipefail' \
        'unset MAVEN_ARGS' \
        'jobs="${HADOOP_MAVEN_THREADS:-$(nproc)}"' \
        'log_file="$(mktemp)"' \
        'status=0' \
        '/opt/maven/bin/mvn -B -ntp -T "${jobs}" -Daether.syncContext.named.time=120 "$@" 2>&1 | tee "${log_file}" || status=$?' \
        'if (( status == 0 )); then' \
        '    rm -f "${log_file}"' \
        '    exit 0' \
        'fi' \
        'if (( jobs <= 1 )) || ! grep -Fq "Could not acquire lock(s)" "${log_file}"; then' \
        '    rm -f "${log_file}"' \
        '    exit "${status}"' \
        'fi' \
        'rm -f "${log_file}"' \
        'printf "%s\n" "Maven resolver lock conflict; retrying this command with one reactor worker."' \
        'exec /opt/maven/bin/mvn -B -ntp -T 1 "$@"' \
        > /opt/hadoop-maven-bin/mvn \
    && chmod +x /opt/hadoop-maven-bin/mvn

# Reuse verified Maven downloads across native and FE build retries. The core
# build below snapshots this repository into the final image for offline tests.
ARG HADOOP_MAVEN_THREADS
RUN --mount=type=cache,id=oss-scanner-doris-4.2-src,target=/src/thirdparty/src,sharing=locked \
    --mount=type=cache,id=oss-scanner-doris-4.2-hadoop-maven,target=/root/.m2/repository,sharing=locked \
    --mount=type=cache,id=oss-scanner-doris-4.2-vcpkg,target=/root/.cache/vcpkg/archives,sharing=locked \
    build_jobs="${NATIVE_BUILD_JOBS:-${BUILD_JOBS:-$(nproc)}}" \
    && hadoop_jobs="${HADOOP_MAVEN_THREADS:-$(nproc)}" \
    && HADOOP_MAVEN_THREADS="${hadoop_jobs}" MAVEN_OPTS="-Xmx${hadoop_jobs}g" \
       PATH="/opt/hadoop-maven-bin:${PATH}" \
       CARGO_BUILD_JOBS="${build_jobs}" \
       bash ./thirdparty/build-thirdparty.sh -j "${build_jobs}" --continue js_and_css

# Retain compiler objects across source checkout and setup retries. The cache
# is separate from the image; the normal native build trees are still retained.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ccache \
    && rm -rf /var/lib/apt/lists/*


# Keep Hadoop's verified bootstrap Maven and use the newer resolver for FE.
RUN curl -fL --retry 3 https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/3.9.16/apache-maven-3.9.16-bin.tar.gz \
        -o /tmp/fe-maven.tar.gz \
    && echo '831a8591fe20c8243b1dbe7d71e3244f31d1665b0804b2e825e38cbbe5ce0cafb8338851f90780735568773e0a6cd07bbec107cda0b896b008b861075358b6f6  /tmp/fe-maven.tar.gz' | sha512sum -c - \
    && mkdir -p /opt/fe-maven \
    && tar -xzf /tmp/fe-maven.tar.gz -C /opt/fe-maven --strip-components=1 \
    && rm /tmp/fe-maven.tar.gz
ENV MAVEN_HOME=/opt/fe-maven
ENV PATH="/opt/fe-maven/bin:$PATH"

# Scanner contract: retain the full checkout, generated bindings, UI dependencies
# and ASan build trees at /src for offline analysis and incremental reproducers.
COPY . /src
ARG DORIS_BUILD_JOBS
ARG FE_BUILD_JOBS
# Four BE submodules share doris-thirdparty's large multi-project history.
# Fetch only each recorded gitlink and initialize independent modules in parallel.
RUN core_jobs="${DORIS_BUILD_JOBS:-$(nproc)}" \
    && git submodule update --init --recursive --depth 1 --jobs "${core_jobs}" -- \
        contrib/datasketches-cpp contrib/apache-orc contrib/clucene \
        contrib/openblas contrib/faiss

# The 4.2 UI uses webpack 4, which needs its legacy hashes on Node's OpenSSL 3.
RUN --mount=type=cache,id=oss-scanner-doris-4.2-hadoop-maven,target=/root/.m2/repository,sharing=locked \
    --mount=type=cache,id=oss-scanner-doris-4.2-ldb-0.25-ccache,target=/var/cache/doris-ccache,sharing=locked \
    --mount=type=cache,id=oss-scanner-doris-4.2-build-logs,target=/var/cache/doris-build-logs,sharing=locked \
    core_jobs="${DORIS_BUILD_JOBS:-$(nproc)}" \
    && fe_jobs="${FE_BUILD_JOBS:-$(nproc)}" \
    && (env -u CCACHE_DISABLE CCACHE_DIR=/var/cache/doris-ccache CCACHE_MAXSIZE=20G \
        FE_MAVEN_THREADS="${fe_jobs}" MAVEN_OPTS="-Xmx${fe_jobs}g" \
        NODE_OPTIONS=--openssl-legacy-provider \
        bash ./build.sh --fe --be --cloud -j "${core_jobs}" 2>&1 \
        | tee /var/cache/doris-build-logs/core.log) \
    || { build_status=$?; tail -n 200 /var/cache/doris-build-logs/core.log >&2; exit "${build_status}"; }; \
    mkdir -p /opt/doris-maven-repository \
    && cp -a /root/.m2/repository/. /opt/doris-maven-repository/

# The cache mount is absent at runtime. Keep Maven's normal repository path
# backed by the snapshot so the scanner can run tests without network access.
RUN mkdir -p /root/.m2 \
    && rm -rf /root/.m2/repository \
    && ln -s /opt/doris-maven-repository /root/.m2/repository

# branch-4.2 defaults this flag to false. Use the authenticated FE HTTP posture
# required by the supplied threat model, without changing the source default.
RUN printf '\n%s\n' 'enable_all_http_auth = true' >> output/fe/conf/fe.conf

COPY <<'PY' /opt/doris-generated-state.py
import hashlib
import json
import os
from pathlib import Path
import sys

root = Path('/src/gensrc/build/gen_cpp')
state_path = Path('/opt/doris-generated-cpp-before-fe-tests.json')
if sys.argv[1:] == ['save']:
    files = []
    for path in sorted(root.iterdir()):
        if not path.is_file():
            continue
        stat = path.stat()
        files.append({'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'atime_ns': stat.st_atime_ns, 'mtime_ns': stat.st_mtime_ns})
    state_path.write_text(json.dumps({'directory': str(root), 'files': files}))
    raise SystemExit(0)

if sys.argv[1:] != ['restore']:
    raise SystemExit('Expected save or restore')

state = json.loads(state_path.read_text())
restored = 0
changed = []
for item in state['files']:
    path = root / item['path']
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
        changed.append(item['path'])
        continue
    os.utime(path, ns=(item['atime_ns'], item['mtime_ns']))
    restored += 1
print(json.dumps({'unchanged_generated_files_restored': restored, 'changed_generated_files_preserved': changed}))
PY
RUN python3 /opt/doris-generated-state.py save

# Exercise the upstream FE unit-test driver online to populate Surefire and its
# test dependencies as well as the runtime dependencies fetched by build.sh.
RUN bash ./run-fe-ut.sh --run org.apache.doris.mysql.MysqlPasswordTest

# Auditing runs offline. Make the normal Maven commands and run-fe-ut.sh use
# only the local repository, then check that the same small test works offline.
RUN mkdir -p /root/.m2 \
    && printf '%s\n' '<settings><offline>true</offline></settings>' > /root/.m2/settings.xml \
    && bash ./run-fe-ut.sh --run org.apache.doris.mysql.MysqlPasswordTest

# FE/BE packages: /src/output/. Cloud package: /src/cloud/output/.
# FE tests: bash ./run-fe-ut.sh --run <class>.
# Native builds: BUILD_TYPE=ASAN bash ./build.sh --be --cloud -j 1.
# Read the enrollment's threat_model.md before exercising services. Keep FE
# enable_all_http_auth=true; check its effective value, including fe_custom.conf,
# and preserve the model's client/internal boundaries.
CMD ["/bin/bash"]

COPY <<'PY' /opt/doris-update-source.py
import filecmp
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def tracked(root):
    entries = git(root, 'ls-files', '--stage', '-z').split(b'\0')
    result = {}
    for entry in entries:
        if not entry:
            continue
        metadata, path = entry.split(b'\t', 1)
        result[os.fsdecode(path)] = metadata.split()[0].decode()
    return result


def native_inputs(root, files):
    result = {}
    for name, mode in files.items():
        if not name.startswith(('thirdparty/', 'gensrc/')) and not name.endswith(('.proto', '.thrift')) and name not in ('env.sh', 'docker/compilation/Dockerfile'):
            continue
        result[name] = [mode, hashlib.sha256((root / name).read_bytes()).hexdigest()]
    return result


def remove(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
        return
    if path.exists():
        shutil.rmtree(path)


root = Path('/src')
state_path = Path('/opt/doris-scanner-source-state.json')
if sys.argv[1:] == ['--record']:
    files = tracked(root)
    state_path.write_text(json.dumps({'revision': git(root, 'rev-parse', 'HEAD').decode().strip(),
                                     'tracked': files, 'native_inputs': native_inputs(root, files)}, sort_keys=True))
    raise SystemExit(0)

checkout = Path('/tmp/doris-checkout')
state = json.loads(state_path.read_text())
files = tracked(checkout)
if native_inputs(checkout, files) != state['native_inputs']:
    raise SystemExit('Doris native dependency or protocol definitions changed. Refresh the builder artifact with the source_build stage.')

removed = set(state['tracked']) - set(files)
for name in removed:
    remove(root / name)

changed = []
for name, mode in files.items():
    if mode == '160000':
        continue
    source = checkout / name
    destination = root / name
    # tools/check intentionally removes the checkout .dockerignore.
    if not source.exists() and not source.is_symlink():
        continue
    if source.is_symlink():
        if destination.is_symlink() and os.readlink(source) == os.readlink(destination):
            continue
        remove(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(os.readlink(source))
        changed.append(name)
        continue
    if destination.is_file() and not destination.is_symlink() and filecmp.cmp(source, destination, shallow=False):
        destination.chmod(source.stat().st_mode & 0o777)
        continue
    remove(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    changed.append(name)

# Drop Java outputs when FE sources change so removed classes cannot survive.
if any(name.startswith('fe/') for name in changed + list(removed)):
    for current, directories, unused_files in os.walk(root / 'fe'):
        if 'target' not in directories:
            continue
        remove(Path(current) / 'target')
        directories.remove('target')

injected = checkout / '.oss-scanner/Dockerfile'
if injected.is_file():
    (root / '.oss-scanner').mkdir(exist_ok=True)
    shutil.copy2(injected, root / '.oss-scanner/Dockerfile')
modules = root / '.git/modules'
saved_modules = Path('/tmp/doris-saved-git-modules')
if modules.exists():
    shutil.move(str(modules), str(saved_modules))
shutil.rmtree(root / '.git')
shutil.copytree(checkout / '.git', root / '.git')
if saved_modules.exists():
    shutil.move(str(saved_modules), str(root / '.git/modules'))
head = git(root, 'rev-parse', 'HEAD').decode().strip()
shutil.rmtree(checkout)
print(json.dumps({'builder_revision': state['revision'], 'checkout_revision': head,
                  'changed_files': len(changed), 'removed_files': len(removed)}))
PY

RUN python3 /opt/doris-generated-state.py restore \
    && python3 /opt/doris-update-source.py --record \
    && cmp be/build_ASAN/src/service/doris_be be/output/lib/doris_be \
    && ln -f be/build_ASAN/src/service/doris_be be/output/lib/doris_be

FROM node:22-bookworm-slim@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        autoconf automake autopoint bash ccache findutils binutils-dev bison byacc bzip2 ca-certificates \
        curl file flex g++ gettext git gperf help2man krb5-user libaio1 \
        libcurl4-openssl-dev libffi-dev libiberty-dev libkrb5-dev libncurses5 \
        libncurses-dev libssl-dev libtool libtool-bin libxml2-dev make \
        mariadb-client nasm openjdk-17-jdk patch pkg-config procps \
        python-is-python3 python3 python3-pip \
        python3-venv texinfo unzip util-linux wget xz-utils zip zlib1g-dev zstd \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 \
    MAVEN_HOME=/opt/fe-maven \
    DORIS_THIRDPARTY=/src/thirdparty \
    DORIS_HOME=/src \
    CARGO_HOME=/opt/cargo \
    RUSTUP_HOME=/opt/rustup \
    REPOSITORY_URL=https://doris-thirdparty-repo.bj.bcebos.com/thirdparty \
    BUILD_TYPE=ASAN \
    USE_AVX2=0 \
    STRIP_DEBUG_INFO=OFF \
    CCACHE_DISABLE=1 \
    FE_MAVEN_THREADS=4 \
    FE_UT_PARALLEL=1 \
    MAVEN_OPTS="-Xmx4g"
ENV PATH="/opt/fe-maven/bin:/opt/cargo/bin:/opt/maven/bin:/usr/lib/jvm/java-17-openjdk-amd64/bin:/var/local/ldb-toolchain/bin:/src/thirdparty/installed/bin:${PATH}"


WORKDIR /src

# The source_build target above refreshes this cache outside the scan's build
# deadline. Each archive part is pinned by SHA256. Source changes still go
# through Doris' normal incremental build, using every available CPU.
ARG DORIS_BUILDER_URL=https://github.com/CalvinKirs/oss-scanner/releases/download/doris-builder-4.2-66122209
COPY <<'PY' /usr/local/lib/doris/check-current-build.py
import json
from pathlib import Path
import subprocess

root = Path('/src')
marker = Path('/tmp/doris-current-build')
marker.unlink(missing_ok=True)
state = json.loads(Path('/opt/doris-scanner-source-state.json').read_text())
head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
if head != state['revision']:
    print('The checkout advanced; run the full upstream build.')
    raise SystemExit(0)

clean = subprocess.run(
    ['git', '-C', str(root), 'diff', '--quiet', '--ignore-submodules=untracked',
     'HEAD', '--', '.', ':(exclude).dockerignore'],
)
if clean.returncode:
    print('Tracked sources changed; run the full upstream build.')
    raise SystemExit(0)

required = [
    root / 'output/be/lib/doris_be',
    root / 'output/fe/lib/doris-fe.jar',
    root / 'cloud/output/lib/doris_cloud',
]
if not all(path.is_file() for path in required):
    print('The packaged build is incomplete; run the full upstream build.')
    raise SystemExit(0)

marker.touch()
print(json.dumps({'reusing_complete_verified_build': head}))
PY

# Native archives reference the existing object files instead of embedding a
# second copy of their full debug information. Verify every member first, then
# losslessly compress object DWARF and retain exact incremental-build timestamps.
COPY <<'PY' /usr/local/lib/doris/thin-archives.py
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess

ar = '/var/local/ldb-toolchain/bin/llvm-ar'
objcopy = '/var/local/ldb-toolchain/bin/llvm-objcopy'
plans = []
for root in [Path('/src/be/build_ASAN'), Path('/src/cloud/build_ASAN')]:
    for archive in sorted((root / 'src').rglob('*.a')):
        relative = archive.relative_to(root)
        query = subprocess.check_output(['ninja', '-C', str(root), '-t', 'query', str(relative)], text=True)
        lines = query.splitlines()
        if len(lines) < 2 or 'STATIC_LIBRARY_LINKER' not in lines[1]:
            continue
        objects = []
        for line in lines[2:]:
            if not line.startswith('    '):
                break
            name = line.strip()
            if name.startswith('|'):
                continue
            if not name.endswith('.o'):
                raise SystemExit('Unexpected static archive input: ' + name)
            objects.append(root / name)
        members = subprocess.check_output([ar, 't', str(archive)], text=True).splitlines()
        if not objects or [Path(name).name for name in members] != [path.name for path in objects]:
            raise SystemExit('Archive members differ from the Ninja object inputs: ' + str(archive))
        expected = hashlib.sha256()
        for path in objects:
            with path.open('rb') as stream:
                while block := stream.read(8 * 1024 * 1024):
                    expected.update(block)
        process = subprocess.Popen([ar, 'p', str(archive)], stdout=subprocess.PIPE)
        actual = hashlib.file_digest(process.stdout, 'sha256').hexdigest()
        process.stdout.close()
        if process.wait() or actual != expected.hexdigest():
            raise SystemExit('Archive contents differ from the retained object files: ' + str(archive))
        plans.append((archive, archive.stat(), objects))


def compress(path):
    stat = path.stat()
    subprocess.run([objcopy, '--preserve-dates', '--compress-debug-sections=zlib', str(path)], check=True)
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    return stat.st_size - path.stat().st_size


objects = sorted({path for archive, stat, members in plans for path in members})
workers = int(os.environ.get('DORIS_BUILD_JOBS') or subprocess.check_output(['nproc'], text=True))
with ThreadPoolExecutor(max_workers=workers) as executor:
    object_savings = sum(executor.map(compress, objects))
converted = []
for archive, stat, objects in plans:
    temporary = archive.with_name(archive.name + '.thin')
    names = [os.path.relpath(path, archive.parent) for path in objects]
    subprocess.run([ar, 'crsT', str(temporary), *names], cwd=archive.parent, check=True)
    if subprocess.check_output([ar, 't', temporary.name], cwd=archive.parent, text=True).splitlines() != names:
        raise SystemExit('Thin archive references differ: ' + str(archive))
    temporary.chmod(stat.st_mode & 0o777)
    os.utime(temporary, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    temporary.replace(archive)
    converted.append({'path': str(archive), 'objects': len(objects), 'saved_bytes': stat.st_size - archive.stat().st_size})
print(json.dumps({'thin_archives': converted, 'archive_bytes_saved': sum(item['saved_bytes'] for item in converted), 'object_bytes_saved': object_savings}))
PY

ARG DORIS_BUILD_JOBS
ARG FE_BUILD_JOBS
# Restore, rebuild and test in one layer so old copies of the large native
# binaries do not consume the runner's disk. Keep the packaged BE independent
# of its intermediate install copy for subsequent upstream build commands.
RUN --mount=type=bind,source=.,target=/incoming,ro \
    mkdir -p /tmp/doris-builder \
    && cd /tmp/doris-builder \
    && printf '%s\n' \
        'f60a54affd7ea6e132ec5e67966f8dcec71abe9b82c39b9aeb9d5560b26050d4  doris-builder.tar.zst.part-00-00' \
        'e754f990b5b37bc726a83a52b66dbca5ee5ae56f50c14709485a99194d69903b  doris-builder.tar.zst.part-00-01' \
        '2fe9980243d7e64cc5a280b0d8254c3e10d7e9c777885bbbdc3c39ba7300a99c  doris-builder.tar.zst.part-00-02' \
        'c52d369340da22e4bac0b9a97ca5b55df27afaa274559e1531f2e527f5609b59  doris-builder.tar.zst.part-00-03' \
        '69865c5ced5df846e0e04df3e2ac84629db9646ee2b622e7fc2a377470bcb790  doris-builder.tar.zst.part-00-04' \
        '0c17d7fad82f721020f07ceb0909a1105a3a216c535e5f57afb16c097a751127  doris-builder.tar.zst.part-00-05' \
        '53c699b424b95b1cfd122698fe9ed00bee352fc645be600cc7a68d76cf039dc7  doris-builder.tar.zst.part-00-06' \
        '35b1e5f04214752c5617795edbae75d130ec8fde9846e99e6a269b2c3bfa6b68  doris-builder.tar.zst.part-00-07' \
        '9d2b1df569a5c52e874ab201369fbc5c62af524661aa1da97d3febb4f7d90d0e  doris-builder.tar.zst.part-00-08' \
        'be9aed427ece6f27c93dc58584d524a95b3754a95b17afbe3962f2659ccfad89  doris-builder.tar.zst.part-00-09' \
        'c8f6dbe63c5126f8322aef2db07cb4d720938b7d9f0722012234f2eb74dae4b9  doris-builder.tar.zst.part-01-00' \
        '4b72f461f4dbe3f99f82068876243df57a3d2443e2629a31f0c8005a26881785  doris-builder.tar.zst.part-01-01' \
        '1c07ad20573a1895b41efdfebfb71f66f203b0ef6523cf61a93f24527f64d694  doris-builder.tar.zst.part-01-02' \
        'dcb3b806e23bb5a8f39cc61e893ef50fb539e6d8e9223ac9c9a1acd6c5a3c248  doris-builder.tar.zst.part-01-03' \
        'c15bc0c49bf34a52efd9218e8a1614fd298efad3dba4975635b3bdd2e9f542c3  doris-builder.tar.zst.part-01-04' \
        'afc7dec9891a00ddb750834ee583aa7e56773abe5733db7ba856db253221f6b7  doris-builder.tar.zst.part-01-05' \
        'b88d9b9197dcafaa4225e3fba889d8898a49960884aba15af7985d9710460ee2  doris-builder.tar.zst.part-01-06' \
        '68f9891b8de2b071a6ada0fd991ad75cc7c3e9c24bd37169686558544492bae5  doris-builder.tar.zst.part-01-07' \
        '0004e14250c80ccdf6f8e98846a03ca9cb69fd64ee7fbbf79ad4f0b223e82c5b  doris-builder.tar.zst.part-01-08' \
        'dc721b09ef2e76fa17251aa2f275ec880397c546f549d94ff3520124d31d7c76  doris-builder.tar.zst.part-01-09' \
        '83dc40299ed9fe9a78cc5eea126dcd942cf636cf6323a7c983fd4f828a2c41f5  doris-builder.tar.zst.part-02' \
        '1e3ab7728d2446717a3e6a6120ea1c330e30a1f691fd88a324705c8618a699d9  doris-builder.tar.zst.part-03-00' \
        'a4939be30f6d081e285d36c4de6ed62632c50f579f88b33e93edebd2f5ef2405  doris-builder.tar.zst.part-03-01' \
        '4d2fc7380374c46b1e96f331ed57086727de259f5964e14560908acb77972ab9  doris-builder.tar.zst.part-03-02' \
        '21976fbc48059719c6179210eb366eaf74213f0ab71f90c86617a080da924985  doris-builder.tar.zst.part-03-03' \
        'b05b1b2807db98738f6506b94fc6c4b70ac1275e173b30cf8b68eb088a130559  doris-builder.tar.zst.part-03-04' \
        'e21d219ff1e07d3a23f75df11dd0f8105acdf8d5f6ed556d84fc782ded34fd72  doris-builder.tar.zst.part-03-05' \
        'fb87ab0b6ac64aca2f89b17e69a864d2be0fab1295303a6a38501a7ee6ac76cc  doris-builder.tar.zst.part-03-06' \
        'e3a9841d70925de31f5a3414b53f73840381b7dff8a3123bd3df2aeceed77ebe  doris-builder.tar.zst.part-03-07' \
        '80fd326cfb629b3e003ae5f434c4133d5daa67fce8712b1f74a85df0bbf52136  doris-builder.tar.zst.part-03-08' \
        'dba00e4ab22013e107c82561996ea2b85d7f0806c570a1561d9eaa50faa77ba4  doris-builder.tar.zst.part-03-09' \
        '6205c87b22d9ea83f208f703f6623e20d6295ab54abadfd1707da4f45168c94d  doris-builder.tar.zst.part-04-00' \
        '1a8a2c1f65ea61d3cf42cddc5be0cf47f56113aeb5f75efda3c3f14c25b9d3d3  doris-builder.tar.zst.part-04-01' \
        '6350430f869769fe59bd3c6e782ac2fed6077b1ce5befdb1c9e0e785448bf028  doris-builder.tar.zst.part-04-02' \
        '2132b8de0c0dc0cc0cda6d35902a55b55160c6e2ab13ca6c8a256b93698b6950  doris-builder.tar.zst.part-04-03' \
        'fa4b139130bf73438d7464bd9a6c4f50c50ad7f5e22c03c5d9758ca417f28586  doris-builder.tar.zst.part-04-04' \
        '848be918eacf7ce8aae996b1c4414a519803333171d7b57c8c7d8263275c7d2e  doris-builder.tar.zst.part-04-05' \
        '43c0dcf10b79976c0adbd96d99794d5f0b46c19ae97e05e62c4a8af60a7eeeaf  doris-builder.tar.zst.part-04-06' \
        'e5bf59bf413278ba89417ebc945b42d3a49d1008940e073e1040e511548855d6  doris-builder.tar.zst.part-04-07' \
        '90c49512b41b860916d2a69bcd6490c7c5068b49db6c34610b7b5f8934559243  doris-builder.tar.zst.part-04-08' \
        '22dcbc0879e912f4db91759d27a0363aff267e6418a9c6258e989ab5a2210d50  doris-builder.tar.zst.part-04-09' \
        'a6606f11ccaff7850ea5cafda649f3130bfe0d7e16b325de94fc081f5dd08f5f  doris-builder.tar.zst.part-05-00' \
        '0768c1b35f7f06a3d23849bebc7ec913334dac43758acd9bd9697ca38b9c9838  doris-builder.tar.zst.part-05-01' \
        'fb5e19f4eb775c52b7c4fea601f3e10974b88068dfe5a62bdeaf7725ea04739a  doris-builder.tar.zst.part-05-02' \
        '681492bdbb373cf342e786e85bb4eb3b5c2807591b22dfbfad49324d03e9a975  doris-builder.tar.zst.part-05-03' \
        '46a5803caa178a374be95bba4e3708e5ab07d93bbabbdf1a2ba61068508e9587  doris-builder.tar.zst.part-05-04' \
        'cae52d82ca812c676d76dcee31d1358db7e26e119d7eb4e377b55d2f2cbe1155  doris-builder.tar.zst.part-05-05' \
        'bd81c08f871f4225d15a7bfad77df1a3b5f6152e07516142b8a12df860031c8e  doris-builder.tar.zst.part-05-06' \
        '49ff52ac9d2fa05ce13d33c6db79c7cfec5f4e760666ad0e6e6940723f2d24b5  doris-builder.tar.zst.part-05-07' \
        'd2e65659920473e7be3a3120031fbb9969202200ec07ebdccbc5c586298ec1e7  doris-builder.tar.zst.part-05-08' \
        '664229a3af4d38400458860d000ad299ebcc53c477f1701892cc22ac3a9a56a6  doris-builder.tar.zst.part-05-09' \
        '0b879fa6ffc252bac77cd22e05c055c003d60fe867bb4d77a002431ab02ac389  doris-builder.tar.zst.part-06-00' \
        '65ce3cf66e59ce88140042406f132836e606f697dec1efbaac3a3a1ef670b055  doris-builder.tar.zst.part-06-01' \
        'c5d9a5eb90036e981f46244c7cc60cbce076653495794db096e18fe4373104f4  doris-builder.tar.zst.part-06-02' \
        '577298a49fecefb10b7928c65cd0bff05a5e0e110a96e9d292ad0b36bff7e725  doris-builder.tar.zst.part-06-03' \
        'dcfc352ebc54078dd8aa240f77bf47c2fdeb624a3c92b8c3da703bb939a591a1  doris-builder.tar.zst.part-06-04' \
        'd82d7be74568e39764f73acc1c3cf3a3ac0b0648e571c833b382e4525896e849  doris-builder.tar.zst.part-06-05' \
        '22098df2eda1522fe9291f213945faf014d5035f2699693301115202dfa8eb43  doris-builder.tar.zst.part-06-06' \
        '6351165c6264b11d37a70ce32c83957b1e2b5c0accdde33af3b82cd863f57ad8  doris-builder.tar.zst.part-06-07' \
        '81ec63b464e4d6e2595b1a1cdca23f2e50fa8b0cf0804f37fec583f77504a7db  doris-builder.tar.zst.part-06-08' \
        '4640c7b38107e834f4a5bcd49da8156af6fa0292ad5b6d42c0c6ac477f2de8ce  doris-builder.tar.zst.part-06-09' \
        'cd4bd1db2d9f0dc54bbb77666633e1c263f209139a41f8919b672c122d8d062e  doris-builder.tar.zst.part-07-00' \
        '7c11bdedaacf684e670cebdaad0684e1058cdbaa840b3f1fd0d1b3eeb0a16049  doris-builder.tar.zst.part-07-01' \
        'fbc052581e898efbe9022ff4976ee7edb3aa11671ecc9ee12b45fe4c5951f4ed  doris-builder.tar.zst.part-07-02' \
        'e7fb3fe38f3c7b55ffc1c8089e9e41f1736ce233a513a22ecb9c6f894f8fcd71  doris-builder.tar.zst.part-07-03' \
        'a4200bb86934a4531013815bce5b64e50489bb6b697f9c20380dabbc890dc6e7  doris-builder.tar.zst.part-07-04' \
        '4f736959427e6e335f2716bcd06c12f4fffa5a6b5524a85de47d582587a02bf8  doris-builder.tar.zst.part-07-05' \
        '95cdd7a2a42cd36f76e7034da17b986e7e8c9c48087fcf5681530140d5c7c38d  doris-builder.tar.zst.part-07-06' \
        '4f52d9ab19251ed6c0debb2276469a608619eaaad632c1d3bb1ca9dd0d8585ff  doris-builder.tar.zst.part-07-07' \
        '5511a54cf2216111f9860b246c54f4d0183d9ed3a8c313a9c91ae40638f71742  doris-builder.tar.zst.part-07-08' \
        'b65eaba3b117560c3fe00a4587eb92f0c73ba1aa119c11696ee6e549d35bf9a7  doris-builder.tar.zst.part-07-09' \
        > SHA256SUMS \
    && printf '%s\n' \
        'doris-builder.tar.zst.part-00-00' \
        'doris-builder.tar.zst.part-00-01' \
        'doris-builder.tar.zst.part-00-02' \
        'doris-builder.tar.zst.part-00-03' \
        'doris-builder.tar.zst.part-00-04' \
        'doris-builder.tar.zst.part-00-05' \
        'doris-builder.tar.zst.part-00-06' \
        'doris-builder.tar.zst.part-00-07' \
        'doris-builder.tar.zst.part-00-08' \
        'doris-builder.tar.zst.part-00-09' \
        'doris-builder.tar.zst.part-01-00' \
        'doris-builder.tar.zst.part-01-01' \
        'doris-builder.tar.zst.part-01-02' \
        'doris-builder.tar.zst.part-01-03' \
        'doris-builder.tar.zst.part-01-04' \
        'doris-builder.tar.zst.part-01-05' \
        'doris-builder.tar.zst.part-01-06' \
        'doris-builder.tar.zst.part-01-07' \
        'doris-builder.tar.zst.part-01-08' \
        'doris-builder.tar.zst.part-01-09' \
        'doris-builder.tar.zst.part-02' \
        'doris-builder.tar.zst.part-03-00' \
        'doris-builder.tar.zst.part-03-01' \
        'doris-builder.tar.zst.part-03-02' \
        'doris-builder.tar.zst.part-03-03' \
        'doris-builder.tar.zst.part-03-04' \
        'doris-builder.tar.zst.part-03-05' \
        'doris-builder.tar.zst.part-03-06' \
        'doris-builder.tar.zst.part-03-07' \
        'doris-builder.tar.zst.part-03-08' \
        'doris-builder.tar.zst.part-03-09' \
        'doris-builder.tar.zst.part-04-00' \
        'doris-builder.tar.zst.part-04-01' \
        'doris-builder.tar.zst.part-04-02' \
        'doris-builder.tar.zst.part-04-03' \
        'doris-builder.tar.zst.part-04-04' \
        'doris-builder.tar.zst.part-04-05' \
        'doris-builder.tar.zst.part-04-06' \
        'doris-builder.tar.zst.part-04-07' \
        'doris-builder.tar.zst.part-04-08' \
        'doris-builder.tar.zst.part-04-09' \
        'doris-builder.tar.zst.part-05-00' \
        'doris-builder.tar.zst.part-05-01' \
        'doris-builder.tar.zst.part-05-02' \
        'doris-builder.tar.zst.part-05-03' \
        'doris-builder.tar.zst.part-05-04' \
        'doris-builder.tar.zst.part-05-05' \
        'doris-builder.tar.zst.part-05-06' \
        'doris-builder.tar.zst.part-05-07' \
        'doris-builder.tar.zst.part-05-08' \
        'doris-builder.tar.zst.part-05-09' \
        'doris-builder.tar.zst.part-06-00' \
        'doris-builder.tar.zst.part-06-01' \
        'doris-builder.tar.zst.part-06-02' \
        'doris-builder.tar.zst.part-06-03' \
        'doris-builder.tar.zst.part-06-04' \
        'doris-builder.tar.zst.part-06-05' \
        'doris-builder.tar.zst.part-06-06' \
        'doris-builder.tar.zst.part-06-07' \
        'doris-builder.tar.zst.part-06-08' \
        'doris-builder.tar.zst.part-06-09' \
        'doris-builder.tar.zst.part-07-00' \
        'doris-builder.tar.zst.part-07-01' \
        'doris-builder.tar.zst.part-07-02' \
        'doris-builder.tar.zst.part-07-03' \
        'doris-builder.tar.zst.part-07-04' \
        'doris-builder.tar.zst.part-07-05' \
        'doris-builder.tar.zst.part-07-06' \
        'doris-builder.tar.zst.part-07-07' \
        'doris-builder.tar.zst.part-07-08' \
        'doris-builder.tar.zst.part-07-09' \
        | xargs -P "$(nproc)" -I '{}' bash -c \
            'curl -fL --retry 3 --connect-timeout 20 --max-time 900 "$1/$2" -o "$2"' _ "$DORIS_BUILDER_URL" '{}' \
    && sha256sum -c SHA256SUMS \
    && cat doris-builder.tar.zst.part-* | zstd -dq --long=31 | tar -xp -C / \
    && cd /src \
    && rm -rf /tmp/doris-builder \
    && cp -a --no-preserve=ownership /incoming /tmp/doris-checkout \
    && python3 /opt/doris-update-source.py \
    && python3 /usr/local/lib/doris/check-current-build.py \
    && core_jobs="$DORIS_BUILD_JOBS" \
    && fe_jobs="$FE_BUILD_JOBS" \
    && if [[ -z "$core_jobs" ]]; then core_jobs="$(nproc)"; fi \
    && if [[ -z "$fe_jobs" ]]; then fe_jobs="$(nproc)"; fi \
    && git submodule update --init --recursive --depth 1 --jobs "$core_jobs" -- \
        contrib/datasketches-cpp contrib/apache-orc contrib/clucene \
        contrib/openblas contrib/faiss \
    && rm -f /root/.m2/settings.xml \
    && if [[ ! -f /tmp/doris-current-build ]]; then \
        FE_MAVEN_THREADS="$fe_jobs" MAVEN_OPTS="-Xmx$fe_jobs"g \
            NODE_OPTIONS=--openssl-legacy-provider \
            bash ./build.sh --fe --be --cloud -j "$core_jobs"; \
       fi \
    && printf '\n%s\n' 'enable_all_http_auth = true' >> output/fe/conf/fe.conf \
    && python3 /opt/doris-generated-state.py save \
    && bash ./run-fe-ut.sh --run org.apache.doris.mysql.MysqlPasswordTest \
    && mkdir -p /root/.m2 \
    && printf '%s\n' '<settings><offline>true</offline></settings>' > /root/.m2/settings.xml \
    && python3 /opt/doris-generated-state.py restore \
    && cmp be/build_ASAN/src/service/doris_be be/output/lib/doris_be \
    && ln -f be/build_ASAN/src/service/doris_be be/output/lib/doris_be \
    && python3 /usr/local/lib/doris/thin-archives.py
CMD ["/bin/bash"]
