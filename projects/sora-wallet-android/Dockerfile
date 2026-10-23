# syntax=docker/dockerfile:1
# Compile actual portable wallet/protocol code and its original JVM tests.
# APK, Android Keystore, UI and live-network qualification are separate; see threat_model.md.
FROM eclipse-temurin:21-jdk-jammy
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git unzip python3 \
    && rm -rf /var/lib/apt/lists/*
ARG KOTLIN_VERSION=2.3.21
ARG KOTLIN_SHA256=a8cfc1d62cd4d0de4d04f42575e40135bd620588c17d568a20eb9c7c259af14f
RUN curl -fsSL -o /tmp/kotlin.zip "https://github.com/JetBrains/kotlin/releases/download/v${KOTLIN_VERSION}/kotlin-compiler-${KOTLIN_VERSION}.zip" \
    && echo "${KOTLIN_SHA256}  /tmp/kotlin.zip" | sha256sum -c - \
    && unzip -q /tmp/kotlin.zip -d /opt && rm /tmp/kotlin.zip
ENV PATH=/opt/kotlinc/bin:$PATH
# Versions match gradle/libs.versions.toml and common/gradle.lockfile.
RUN <<'SH'
set -eu
mkdir -p /opt/scanner/lib
while read -r checksum artifact; do
    output="/opt/scanner/lib/${artifact##*/}"
    curl -fsSL -o "$output" "https://repo.maven.apache.org/maven2/$artifact"
    echo "$checksum  $output" | sha256sum -c -
done <<'DEPS'
8e495b634469d64fb8acfa3495a065cbacc8a0fff55ce1e31007be4c16dc57d3 junit/junit/4.13.2/junit-4.13.2.jar
66fdef91e9739348df7a096aa384a5685f4e875584cce89386a7a47251c4d8e9 org/hamcrest/hamcrest-core/1.3/hamcrest-core-1.3.jar
91c77044a50c481636c32d916fd89c9118a72195390452c81065080f957de7ff javax/inject/javax.inject/1/javax.inject-1.jar
dd0ce1b55a3ed2080cb70f9c655850cda86c206862310009dcb5e5c95265a5e0 com/google/code/gson/gson/2.13.2/gson-2.13.2.jar
add5915e6acfc6ab5836e1fd8a5e21c6488536a8c1f21f386eeb3bf280b702d7 org/bouncycastle/bcprov-jdk18on/1.78.1/bcprov-jdk18on-1.78.1.jar
1f0afa172110e45a7231ef1b44ae8fd84c1ebaff96f3fc3ad68ef8c48120b59c org/jetbrains/kotlinx/kotlinx-serialization-core-jvm/1.9.0/kotlinx-serialization-core-jvm-1.9.0.jar
d94cc34cae39246a1af74fda63f9c4812ce12216ef641d5fa3bbbb539a6922d8 org/jetbrains/kotlinx/kotlinx-serialization-json-jvm/1.9.0/kotlinx-serialization-json-jvm-1.9.0.jar
5ca175b38df331fd64155b35cd8cae1251fa9ee369709b36d42e0a288ccce3fd org/jetbrains/kotlinx/kotlinx-coroutines-core-jvm/1.10.2/kotlinx-coroutines-core-jvm-1.10.2.jar
DEPS
SH
COPY . /src
WORKDIR /src
COPY <<'TESTS' /opt/scanner/test-classes
jp.co.soramitsu.common.nexus.TairaTestnetContractTest
jp.co.soramitsu.common.nexus.TairaTransferCodecTest
jp.co.soramitsu.common.nexus.NexusMcpContractTest
jp.co.soramitsu.common.nexus.NexusAccountTransactionProofTest
jp.co.soramitsu.common.nexus.NexusToriiRoutesTest
jp.co.soramitsu.common.nexus.NexusBalanceValidatorTest
jp.co.soramitsu.common.nexus.NexusQuantityContractTest
jp.co.soramitsu.common.nexus.TairaCurrentContractTest
jp.co.soramitsu.common.nexus.TairaSigningClientTest
jp.co.soramitsu.common.nexus.NexusTransferHistoryParserTest
jp.co.soramitsu.common.nexus.TairaToriiQueriesTest
jp.co.soramitsu.common.nexus.NexusDirectToriiReadTest
jp.co.soramitsu.common.network.StrictJsonDocumentAdmissionTest
jp.co.soramitsu.common.network.BoundedHttpTextClientTest
TESTS
COPY --chmod=0755 <<'SH' /usr/local/bin/scanner-core-build
#!/bin/sh
set -eu
cd /src
main=common/src/main/java/jp/co/soramitsu/common
set -- "$main/nexus/IrohaAddressCodec.kt" "$main/nexus/NexusNetwork.kt" \
    "$main/nexus/NexusQuantityContract.kt" "$main/nexus/NexusTransactionHash.kt" \
    "$main/nexus/NexusToriiRoutes.kt" "$main/nexus/NexusTransferHistory.kt" \
    "$main/nexus/TairaMcpContract.kt" "$main/nexus/TairaSigningClient.kt" \
    "$main/nexus/TairaTransferCodec.kt" "$main/nexus/NexusToriiClient.kt" \
    "$main/network/BoundedHttpTextClient.kt" "$main/network/StrictJsonDocumentAdmission.kt"
while read -r test_class; do
    source_path=$(printf '%s' "$test_class" | tr . /)
    # This original test class has a different filename in the application repo.
    case "$test_class" in
        *.TairaTestnetContractTest) source_path=jp/co/soramitsu/common/nexus/TairaDeploymentBindingTest ;;
    esac
    set -- "$@" "common/src/test/java/$source_path.kt"
done < /opt/scanner/test-classes
classpath=$(printf '%s:' /opt/scanner/lib/*.jar)
JAVA_OPTS='-Xmx2g -XX:ActiveProcessorCount=2' kotlinc -jvm-target 17 \
    -Xplugin=/opt/kotlinc/lib/kotlinx-serialization-compiler-plugin.jar \
    -cp "${classpath%:}" "$@" -include-runtime -d /opt/scanner/wallet-core-tests.jar
SH
COPY --chmod=0755 <<'SH' /usr/local/bin/scanner-core-test
#!/bin/sh
set -eu
cd /src
set --
while read -r test_class; do set -- "$@" "$test_class"; done < /opt/scanner/test-classes
exec java -Xmx2g -XX:ActiveProcessorCount=2 \
    -cp '/opt/scanner/wallet-core-tests.jar:/opt/scanner/lib/*:/src/common/src/test/resources' \
    org.junit.runner.JUnitCore "$@"
SH
# All compiler/dependency downloads finish before this explicitly offline build and test.
RUN --network=none scanner-core-build && scanner-core-test
# Compiler, serialization plugin, libraries, fixtures and test binary remain for reproducers.
