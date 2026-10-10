# syntax=docker/dockerfile:1
# The official postgres image, because pgjdbc's own test server scripts in
# docker/postgres-server/scripts are written against its docker-entrypoint.sh.
FROM postgres:17-trixie
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git openjdk-21-jdk-headless \
    && rm -rf /var/lib/apt/lists/*

# Same defaults as docker/postgres-server/docker-compose.yml. entrypoint.sh runs with set -u,
# so every variable it reads has to be set.
ENV SSL=yes XA=yes SCRAM=yes TZ=Etc/UTC \
    FSYNC=no SYNC_COMMIT=yes FULL_PAGE_WRITES=no AUTO_VACUUM=no TRACK_COUNTS=no \
    CREATE_REPLICAS=no STANDARD_CONFORMING_STRINGS=yes \
    POSTGRES_USER=postgres POSTGRES_PASSWORD= POSTGRES_DB=postgres \
    POSTGRES_HOST_AUTH_METHOD=trust

# Starts the test server the way CI does, but in the background, and waits for it to accept
# connections. The scripts and certificates are copied from /src on each start so edits there
# take effect. entrypoint.sh appends to its own copy of pg_hba.conf, so that copy is removed
# first.
COPY <<'EOF' /usr/local/bin/pgjdbc-test-db
#!/bin/bash
set -eu
if (exec 3<>/dev/tcp/127.0.0.1/5432) 2>/dev/null; then
  exit 0
fi
rm -rf /custom /home/certdir
mkdir -p /custom
cp -r /src/docker/postgres-server/scripts /custom/scripts
cp -r /src/certdir/server /custom/certdir
nohup bash /custom/scripts/entrypoint.sh postgres >/var/log/pgjdbc-test-db.log 2>&1 &
for _ in $(seq 120); do
  if (exec 3<>/dev/tcp/127.0.0.1/5432) 2>/dev/null; then
    exit 0
  fi
  sleep 1
done
echo "pgjdbc-test-db: server did not start, see /var/log/pgjdbc-test-db.log" >&2
exit 1
EOF
RUN chmod 0755 /usr/local/bin/pgjdbc-test-db

COPY . /src
WORKDIR /src
# The test server has SSL on, so turn on the SSL tests the way CI does.
RUN echo enable_ssl_tests=true > ssltest.local.properties

# Build the driver and test classes. Checkstyle, forbidden-apis and Javadoc are skipped: they
# only fetch tools the scan does not need.
ENV GRADLE_OPTS="-Dorg.gradle.daemon=false" \
    PGJDBC_GRADLE_FLAGS="-PskipJavadoc -PskipCheckstyle -PskipForbiddenApis -PjdkBuildVersion=0"
RUN ./gradlew $PGJDBC_GRADLE_FLAGS :postgresql:jar :postgresql:testClasses

# Run a couple of test classes against the test server. This also resolves the test runtime
# dependencies into ~/.gradle so later runs work with --offline.
RUN pgjdbc-test-db \
    && (timeout 900 ./gradlew $PGJDBC_GRADLE_FLAGS :postgresql:test \
          --tests org.postgresql.core.ParserTest \
          --tests org.postgresql.test.jdbc2.ConnectionTest \
        || echo "WARNING: pgjdbc tests reported failures") \
    ; gosu postgres pg_ctl -D "$PGDATA" -m fast stop
