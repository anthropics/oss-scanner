# RSKj (https://github.com/rsksmart/rskj), the reference node implementation of Rootstock: a
# Bitcoin merge-mined sidechain with an EVM-compatible execution layer and a two-way BTC peg.
#
# This file sits beside project.yaml, so the scanner copies THIS FILE AND NOTHING ELSE from this
# directory into the checkout, at .oss-scanner/Dockerfile, and removes the repository's own
# .dockerignore before building with the checkout as the context (tools/check_build.py). Anything
# the build needs that RSKj does not already carry therefore has to be written inline below --
# hence the two `printf` blocks rather than files next to this one.
#
# The contract this file honours:
#   * the checkout lives at /src and is already built there (`COPY . /src` + WORKDIR /src);
#   * the final stage keeps a package manager, because the scanner's tools layer installs into it
#     (eclipse-temurin is Ubuntu-based, so apt-get is there);
#   * the build fits in 45 minutes on 16 CPUs / 64 GB, so the full suite is out and only a smoke
#     subset runs here;
#   * the audit itself runs on 2 CPUs / 8 GB with no network at all.
#
# This is deliberately not RSKj's own root Dockerfile: that one builds the published node image, a
# slim JRE holding only rsk.jar, and keeps neither the sources nor the Gradle cache an offline
# audit needs.

# The same digest RSKj's root Dockerfile pins for its build stage.
FROM eclipse-temurin:17-jdk@sha256:0613a19436dc8f745914b25235d43f3b0eddb8d432d19edce30ffaf2d2f95403

# LANG, not JAVA_TOOL_OPTIONS: the latter makes every JVM print "Picked up JAVA_TOOL_OPTIONS" to
# stderr, which would contaminate the test output and node logs the auditing agent has to read.
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8

# GRADLE_USER_HOME is set explicitly rather than left at ~/.gradle: the build below runs as root,
# but it is an ENV so the cache is still found whatever user the scanner's layer or the agent ends
# up as. Without this a change of home silently re-points Gradle at an empty, un-fillable cache.
ENV GRADLE_USER_HOME=/opt/gradle-home \
    GRADLE_OPTS="-Dorg.gradle.daemon=false"

# `ca-certificates curl git gnupg` are what the build itself needs. The rest are the packages the
# scanner's own layer tries to install anyway -- putting them here means the audit still has them
# if that best-effort step is ever trimmed.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        file \
        git \
        gnupg \
        jq \
        less \
        procps \
        python3 \
        unzip \
        xxd \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# configure.sh fetches gradle/wrapper/gradle-wrapper.jar, which RSKj does not commit, and checks it
# against a pinned SHA-256. Verify configure.sh itself first, exactly as the project's own
# .github/workflows/build_and_test.yml and its reproducible-build recipe do, so that a tampered
# checkout cannot smuggle in a wrapper.
RUN curl -sSL https://secchannel.rsk.co/SUPPORT.asc | gpg --import - \
 && gpg --verify --output SHA256SUMS SHA256SUMS.asc \
 && sha256sum --check SHA256SUMS \
 && rm -f SHA256SUMS \
 && ./configure.sh

# Compile everything, including all three test source sets, and build the fat jar (`assemble`
# covers it via `artifacts { archives fatJar }`). This is the step that must not fail: if RSKj does
# not compile there is nothing to audit.
RUN ./gradlew --no-daemon --stacktrace assemble testClasses integrationTestClasses fuzzTestClasses

# RSKj has no task that resolves every dependency, and compiling touches neither the runtime
# classpaths, nor the JaCoCo agent, nor the Checkstyle tool. This init script adds one: it walks
# every project and resolves every resolvable configuration. Under -PossScannerStrict it fails on
# any configuration it could not resolve, which is what makes the offline check further down a
# real proof rather than a hope.
RUN mkdir -p /opt/oss-scanner && printf '%s\n' \
  'gradle.rootProject { root ->' \
  '  root.tasks.register("ossScannerPrefetch") {' \
  '    group = "oss-scanner"' \
  '    doLast {' \
  '      def resolved = 0' \
  '      def skipped = []' \
  '      root.allprojects.each { p ->' \
  '        p.configurations.each { c ->' \
  '          if (!c.canBeResolved) { return }' \
  '          try { c.resolve(); resolved++ }' \
  '          catch (Exception e) { skipped << "${p.path}:${c.name}: ${e.message}".toString() }' \
  '        }' \
  '      }' \
  '      logger.lifecycle("prefetch: resolved ${resolved} configuration(s), skipped ${skipped.size()}")' \
  '      skipped.each { logger.lifecycle("prefetch: SKIPPED ${it}") }' \
  '      if (!skipped.isEmpty() && root.hasProperty("ossScannerStrict")) {' \
  '        throw new GradleException("prefetch: ${skipped.size()} configuration(s) did not resolve")' \
  '      }' \
  '    }' \
  '  }' \
  '}' \
  > /opt/oss-scanner/prefetch.gradle

RUN ./gradlew --no-daemon -I /opt/oss-scanner/prefetch.gradle ossScannerPrefetch

# Checkstyle and Spotless resolve part of their classpath lazily, at task execution, so `check` has
# to run once to warm it. Its *result* is deliberately not a gate: a style regression on the
# default branch must not cost the project an entire security scan.
RUN ./gradlew --no-daemon check -x test \
    || echo "WARNING: ./gradlew check reported failures; caches are warm, continuing"

# Run a couple of cheap, deterministic unit tests. This is what pulls the JUnit platform launcher,
# the JUnit 5 engine and the JaCoCo agent (`test` is finalizedBy jacocoTestReport) into the cache:
# compiling test code alone does not. Not a gate either -- a flaky test is no reason to drop an
# audit.
RUN ./gradlew --no-daemon test \
        --tests 'co.rsk.util.HexUtilsTest' \
        --tests 'org.ethereum.util.ByteUtilTest' \
    || echo "WARNING: the smoke test run reported failures; caches are warm, continuing"

# From here on every Gradle invocation is offline by default, so that a forgotten --offline during
# the audit cannot stall on a repository lookup. The projectsLoaded line prints the flag it set, so
# the build log shows this script was actually read -- without it, a silently ignored init script
# would look exactly like a working one for as long as the network is still up.
RUN mkdir -p "$GRADLE_USER_HOME/init.d" && printf '%s\n' \
  'gradle.startParameter.offline = true' \
  'gradle.projectsLoaded {' \
  '  gradle.rootProject.logger.lifecycle("oss-scanner: gradle offline=" + gradle.startParameter.offline)' \
  '}' \
  > "$GRADLE_USER_HOME/init.d/offline.gradle"

# The two acceptance checks for this file, both hard gates. They pass --offline explicitly rather
# than leaning on the init script above: the network is still up at this point, so only an
# explicit --offline makes a pass here mean anything.
#
#   1. every configuration resolves from the cache alone (-PossScannerStrict fails on any that does
#      not), which covers integrationTest and fuzzTest without running either;
#   2. a real test executes, which covers the JUnit launcher and the JaCoCo agent.
RUN ./gradlew --no-daemon --offline -I /opt/oss-scanner/prefetch.gradle ossScannerPrefetch -PossScannerStrict \
 && ./gradlew --no-daemon --offline test --tests 'co.rsk.util.HexUtilsTest'

# Notes for the auditing agent, in the directory this Dockerfile was placed in.
RUN printf '%s\n' \
  '# Working in the OSS Scanner image' \
  '' \
  'RSKj is already built at `/src` and the Gradle cache is warm. There is **no network**, but you' \
  'do not need to remember `--offline`: an init script in $GRADLE_USER_HOME/init.d already sets it' \
  'for every invocation.' \
  '' \
  '    ./gradlew --no-daemon test --tests "co.rsk.peg.BridgeSupportTest"   # one unit test class' \
  '    ./gradlew --no-daemon assemble                                     # rebuild after an edit' \
  '' \
  'Fat jar: `rskj-core/build/libs/rskj-core-<version>-<modifier>-all.jar`' \
  '' \
  '## A local node' \
  '' \
  'A standalone regtest node needs no peers, mines on its own, and serves JSON-RPC on' \
  '`127.0.0.1:4444`. It is usually the quickest way to reproduce something end to end.' \
  '' \
  '    java -Dlogging.stdout=INFO -Dpublic.ip=127.0.0.1 \' \
  '         -cp rskj-core/build/libs/rskj-core-*-all.jar co.rsk.Start --regtest' \
  '' \
  'Keep `-Dpublic.ip`. Without it the node queries `checkip.amazonaws.com` for its public IP;' \
  'offline that stalls on DNS and logs an ERROR stack trace. The node recovers by falling back to' \
  '`127.0.0.1` (`SystemProperties.getMyPublicIpFromRemoteService`), so that error is an artefact of' \
  'the sandbox, not a fault worth reporting.' \
  '' \
  'Regtest activates upgrades that are not active on mainnet and enables the wallet: check any' \
  'finding against the mainnet config before rating it.' \
  '' \
  '## Resources' \
  '' \
  'This VM has 2 CPUs and 8 GB, and the `test` task asks for `-Xmx4G`. Keep `--tests` selections' \
  'narrow, and do not use the `parallelTest` task.' \
  '' \
  'The `integrationTest` suite spawns real node processes and binds ports. Its dependencies are' \
  'cached, but it is slow and is rarely needed to reproduce a finding.' \
  > /src/.oss-scanner/AGENT-NOTES.md

CMD ["bash"]
