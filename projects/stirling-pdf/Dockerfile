# syntax=docker/dockerfile:1
# The same base image the release images use: LibreOffice (sandboxed), qpdf 12, Ghostscript,
# Tesseract, OCRmyPDF, WeasyPrint, unoserver, ImageMagick and Calibre. It ships a JRE, so a JDK is added.
FROM eclipse-temurin:25-jdk-noble AS jdk
FROM stirlingtools/stirling-pdf-base:1.1.0
USER 0
COPY --from=jdk /opt/java/openjdk /opt/java/openjdk
RUN apt-get update && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Backend only: the React frontend is built separately and is not needed to run the API.
ENV GRADLE_OPTS="-Dorg.gradle.daemon=false" \
    SPDF_GRADLE_FLAGS="-PbuildWithFrontend=false -PjpdfiumPlatforms=linux-x64 -x spotlessApply -x spotlessCheck"
# Same compiler exports as docker/backend/Dockerfile.
ENV JDK_JAVA_OPTIONS="--add-exports=jdk.compiler/com.sun.tools.javac.api=ALL-UNNAMED \
  --add-exports=jdk.compiler/com.sun.tools.javac.file=ALL-UNNAMED \
  --add-exports=jdk.compiler/com.sun.tools.javac.parser=ALL-UNNAMED \
  --add-exports=jdk.compiler/com.sun.tools.javac.tree=ALL-UNNAMED \
  --add-exports=jdk.compiler/com.sun.tools.javac.util=ALL-UNNAMED"

# Build the runnable jar and every module's test classes.
RUN ./gradlew $SPDF_GRADLE_FLAGS :stirling-pdf:bootJar testClasses

# Run a few test classes so the test runtime deps land in ~/.gradle for later --offline runs.
RUN (timeout 900 ./gradlew $SPDF_GRADLE_FLAGS \
      :common:test --tests 'stirling.software.common.util.CustomHtmlSanitizerTest' \
      :stirling-pdf:test --tests 'stirling.software.SPDF.controller.api.MergeControllerTest' \
      :proprietary:test --tests '*ApiKeyAuthenticationServiceTest' \
    || echo "WARNING: Stirling-PDF tests reported failures")

# Lay the app out like docker/backend/Dockerfile so /scripts/init.sh starts it with unoserver.
ENV STIRLING_TEMPFILES_DIRECTORY=/tmp/stirling-pdf TMPDIR=/tmp/stirling-pdf \
    STIRLING_AOT_ENABLE=false HOME=/home/stirlingpdfuser \
    DBUS_SESSION_BUS_ADDRESS=/dev/null SAL_TMP=/tmp/stirling-pdf/libre
RUN set -eux; \
    cp "$(ls app/core/build/libs/stirling-pdf-*.jar | grep -v plain | head -1)" /app.jar; \
    mkdir -p /app /scripts /logs /configs /customFiles /pipeline /storage /tmp/stirling-pdf; \
    for d in logs configs customFiles pipeline storage; do ln -s /$d /app/$d; done; \
    chown stirlingpdfuser:stirlingpdfgroup /app; \
    cp scripts/*.sh /scripts/ && chmod +x /scripts/*.sh
# Starts the full app in the background and waits for the API, as the release image would run it.
COPY <<'EOF2' /usr/local/bin/stirling-pdf-start
#!/bin/bash
set -u
if curl -sf -o /dev/null http://localhost:8080/api/v1/info/status; then exit 0; fi
cp "$(ls /src/app/core/build/libs/stirling-pdf-*.jar | grep -v plain | head -1)" /app.jar
cd /app && nohup /scripts/init.sh >/var/log/stirling-pdf.log 2>&1 &
for _ in $(seq 180); do
  curl -sf -o /dev/null http://localhost:8080/api/v1/info/status && exit 0
  sleep 1
done
echo "stirling-pdf-start: app did not start, see /var/log/stirling-pdf.log" >&2
exit 1
EOF2
RUN chmod 0755 /usr/local/bin/stirling-pdf-start
