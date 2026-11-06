# syntax=docker/dockerfile:1
FROM ghcr.io/reddit/thrift-compiler:0.13.0@sha256:571921dae3a778e1e512ee0d709e9abf2fded77e8a33f257c0411e2f48ba7334 AS thrift
FROM eclipse-temurin:25-jdk-noble

RUN apt-get update && apt-get install -y --no-install-recommends git libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=thrift /usr/local/bin/thrift /usr/local/bin/thrift

COPY . /src
WORKDIR /src

COPY <<'EOF' /root/.gradle/init.d/oss-scanner.gradle
import org.gradle.api.artifacts.component.ModuleComponentIdentifier
import org.gradle.api.tasks.Exec

allprojects { p ->
    // Docker is unavailable inside the scanner's build container, so generate
    // Thrift fixtures by invoking the compiler directly.
    if (p.path == ":instrumentation:thrift-0.13:testing") {
        p.afterEvaluate {
            p.tasks.named("generateThriftSources", Exec) {
                commandLine("/usr/local/bin/thrift", "--gen", "java", "-out",
                    p.layout.buildDirectory.dir("generated/thrift/main").get().asFile,
                    p.file("src/main/thrift/custom.thrift"))
            }
        }
    }

    p.tasks.register("ossScannerResolveTestRuntime") {
        notCompatibleWithConfigurationCache("Resolves test runtime configurations at execution time")
        doLast {
            // The coverage JVM agent is resolved separately from test runtime classpaths.
            p.configurations.findAll {
                it.canBeResolved && (
                    (it.name.toLowerCase().contains("test") && it.name.endsWith("RuntimeClasspath")) ||
                        it.name == "jacocoAgent")
            }.each { configuration ->
                // Project artifacts are built from source; cache external dependencies for offline use.
                configuration.incoming.artifactView {
                    componentFilter { it instanceof ModuleComponentIdentifier }
                }.files.files
            }
        }
    }
}
EOF

RUN ./gradlew --no-daemon --console=plain \
    "-Dorg.gradle.jvmargs=-Xmx8g -XX:MaxMetaspaceSize=1g" \
    classes testClasses :javaagent:assemble \
    && ./gradlew --no-daemon --console=plain --no-configuration-cache \
    "-Dorg.gradle.jvmargs=-Xmx8g -XX:MaxMetaspaceSize=1g" \
    ossScannerResolveTestRuntime

RUN mkdir -p /root/.gradle/init.d \
    && printf '%s\n' 'gradle.startParameter.offline = true' \
    > /root/.gradle/init.d/oss-scanner-offline.gradle
