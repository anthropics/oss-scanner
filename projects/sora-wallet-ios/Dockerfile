# syntax=docker/dockerfile:1
# Build the application's Nexus codec, fee authorization and faucet state machine.
# The untouched Apple transport and app sources remain available at /src.
FROM swift:6.1-jammy
# The scanner installs Ubuntu Clang over /usr/bin/clang and /usr/bin/clang++.
# Select Swift's versioned compiler through stable links before that happens;
# its original location also retains the matching Clang resource directory.
RUN mkdir -p /opt/swift-toolchain/bin \
    && ln -s "$(readlink -f "$(command -v clang)")" /opt/swift-toolchain/bin/clang \
    && ln -s "$(readlink -f "$(command -v clang++)")" /opt/swift-toolchain/bin/clang++ \
    && test -d "$(/opt/swift-toolchain/bin/clang -print-resource-dir)"
ENV CC=/opt/swift-toolchain/bin/clang \
    CXX=/opt/swift-toolchain/bin/clang++ \
    PATH=/opt/swift-toolchain/bin:$PATH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git python3 curl \
    && rm -rf /var/lib/apt/lists/*
COPY . /src
WORKDIR /src
COPY <<'SWIFT' /opt/scanner/Package.swift
// swift-tools-version: 5.9
import PackageDescription
let package = Package(
    name: "SoraWalletScanner",
    dependencies: [.package(url: "https://github.com/apple/swift-crypto.git", exact: "3.9.1")],
    targets: [
        .target(name: "NexusTransferCodec", dependencies: [.product(name: "Crypto", package: "swift-crypto")]),
        .testTarget(name: "NexusTransferCodecTests", dependencies: ["NexusTransferCodec", .product(name: "Crypto", package: "swift-crypto")],
                    resources: [.copy("transfer.json"), .copy("faucet-prepared.json")])
    ]
)
SWIFT
COPY --chmod=0755 <<'SH' /usr/local/bin/scanner-core-build
#!/bin/sh
set -eu
# Adapt only copies in the harness. The scanner sees the complete original repo.
python3 - <<'PY'
from pathlib import Path
import re
import shutil

original = Path('/src/VendorPackages/NexusTransferCodec')
harness = Path('/opt/scanner')
for folder in ['Sources', 'Tests']:
    shutil.rmtree(harness / folder, ignore_errors=True)
    shutil.copytree(original / folder, harness / folder)
crypto_imports = core_imports = network_imports = transport_adapters = 0
for source in sorted(harness.glob('**/*.swift')):
    if source.name == 'Package.swift' or '.build' in source.parts:
        continue
    text = source.read_text()
    text, count = re.subn(r'(?m)^import CryptoKit$', 'import Crypto', text)
    crypto_imports += count
    if 'CFGetTypeID' in text:
        assert 'import Foundation\n' in text
        text = text.replace('import Foundation\n', 'import Foundation\nimport CoreFoundation\n', 1)
        core_imports += 1
    if 'URLRequest' in text:
        assert 'import Foundation\n' in text
        text = text.replace('import Foundation\n', 'import Foundation\nimport FoundationNetworking\n', 1)
        network_imports += 1
    if source.name in ['TairaClient.swift', 'TairaFaucetClient.swift']:
        # URLSession.bytes(for:) is Apple-only. Preserve the complete original
        # implementation under the platform branch; Linux's default transport
        # refuses network use. All original tests inject their own transports.
        first = '        let (stream, response) = try await session.bytes(for: request)'
        assert text.count(first) == 1
        end = ('        return data' if source.name == 'TairaClient.swift' else
               '        return Response(data: data, statusCode: http.statusCode, retryAfterSeconds: retry)')
        assert text.count(end) == 1
        text = text.replace(first, '        #if !os(Linux)\n' + first, 1)
        text = text.replace(end, end + '\n        #else\n        throw Failure.invalidResponse\n        #endif', 1)
        transport_adapters += 1
    source.write_text(text)
assert crypto_imports == 7, f'Expected seven CryptoKit imports, got {crypto_imports}'
assert core_imports == 1, f'Expected one CoreFoundation import, got {core_imports}'
assert network_imports == 3, f'Expected three network imports, got {network_imports}'
assert transport_adapters == 2, f'Expected two Apple transport adapters, got {transport_adapters}'
PY
cd /opt/scanner
swift test --jobs 2
SH
COPY --chmod=0755 <<'SH' /usr/local/bin/scanner-core-test
#!/bin/sh
set -eu
cd /opt/scanner
exec swift test --skip-build --skip-update
SH
RUN scanner-core-build
