# syntax=docker/dockerfile:1
# OpenOlat with PostgreSQL and Tomcat in one image. `openolat-start` runs it on http://localhost:8088/.
FROM eclipse-temurin:17-jdk-noble

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG MAVEN_VERSION=3.9.9
ARG MAVEN_SHA512=a555254d6b53d267965a3404ecb14e53c3827c09c3b94b5678835887ab404556bfaf78dcfe03ba76fa2508649dca8531c74bca4d5846513522404d48e8c4ac8b
ARG TOMCAT_VERSION=10.1.57
ARG TOMCAT_SHA512=2fa1866ec647d4222b07ea937a4cc266adee219a1a8870107e72fc2349248dd1e32b157fa18108451f4c6e3b162f0fdfbdd11dd7855d4e49a2f0f609004a77f3
ARG PLAYWRIGHT_VERSION=1.48.0

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    TZ=Europe/Zurich \
    MAVEN_OPTS="-Xmx3g" \
    CATALINA_HOME=/opt/tomcat \
    CATALINA_PID=/opt/tomcat/temp/tomcat.pid \
    CATALINA_OPTS="-Xmx2g -XX:MaxMetaspaceSize=768m -Djava.awt.headless=true -Duser.timezone=Europe/Zurich" \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright \
    PATH=/opt/playwright-venv/bin:/opt/maven/bin:/opt/tomcat/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
         ca-certificates curl git unzip tzdata postgresql python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL "https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz" -o /tmp/maven.tgz \
    && echo "${MAVEN_SHA512}  /tmp/maven.tgz" | sha512sum -c - \
    && mkdir /opt/maven && tar -xzf /tmp/maven.tgz -C /opt/maven --strip-components=1 \
    && curl -fsSL "https://archive.apache.org/dist/tomcat/tomcat-10/v${TOMCAT_VERSION}/bin/apache-tomcat-${TOMCAT_VERSION}.tar.gz" -o /tmp/tomcat.tgz \
    && echo "${TOMCAT_SHA512}  /tmp/tomcat.tgz" | sha512sum -c - \
    && mkdir /opt/tomcat && tar -xzf /tmp/tomcat.tgz -C /opt/tomcat --strip-components=1 \
    && rm -rf /tmp/*.tgz /opt/tomcat/webapps/*

# Headless Chromium for driving the web UI. The venv is first on PATH, so `python3` can import playwright.
RUN python3 -m venv /opt/playwright-venv \
    && pip install --no-cache-dir "playwright==${PLAYWRIGHT_VERSION}" \
    && playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

# Tomcat 10.1 limits form fields and multipart parts by default; OpenOlat forms and uploads need more.
COPY <<'EOF' /opt/tomcat/conf/server.xml
<Server port="8005" shutdown="SHUTDOWN">
  <Service name="Catalina">
    <Connector port="8088" URIEncoding="UTF-8" maxParameterCount="-1" maxPartCount="-1" />
    <Engine name="Catalina" defaultHost="localhost">
      <Host name="localhost" appBase="webapps" autoDeploy="false" />
    </Engine>
  </Service>
</Server>
EOF

# Tomcat's lib/ is on the classpath, where OpenOlat looks for olat.local.properties.
COPY <<'EOF' /opt/tomcat/lib/olat.local.properties
userdata.dir=/opt/olatdata
db.vendor=postgresql
db.name=openolat
db.user=openolat
db.pass=openolat
db.host.port=5432
server.domainname=localhost
server.port=8088
server.port.ssl=0
smtp.host=disabled
restapi.enable=true
EOF

# Starts PostgreSQL and Tomcat (as user openolat). Redeploys when /src/target has a WAR newer than the deployed one.
COPY <<'EOF' /usr/local/bin/openolat-start
#!/bin/bash
set -euo pipefail
service postgresql start > /dev/null
curl -sf -o /dev/null http://localhost:8088/dmz/ && exit 0
WAR="$(ls -t /src/target/openolat-lms-*.war | head -1)"
ROOT=/opt/tomcat/webapps/ROOT
if [ "${WAR}" -nt "${ROOT}/.deployed" ]; then
  rm -rf "${ROOT}" /opt/tomcat/work/*
  unzip -q "${WAR}" -d "${ROOT}" && touch "${ROOT}/.deployed"
  chown -R openolat /opt/tomcat /opt/olatdata
fi
runuser -u openolat -- /opt/tomcat/bin/catalina.sh start > /dev/null
for _ in $(seq 600); do
  curl -sf -o /dev/null http://localhost:8088/dmz/ && { echo "OpenOlat is up on http://localhost:8088/"; exit 0; }
  sleep 1
done
tail -n 100 /opt/tomcat/logs/catalina.out >&2
exit 1
EOF

COPY <<'EOF' /usr/local/bin/openolat-stop
#!/bin/bash
[ -f "${CATALINA_PID}" ] && runuser -u openolat -- /opt/tomcat/bin/catalina.sh stop 60 -force > /dev/null
service postgresql stop > /dev/null
exit 0
EOF

RUN chmod 0755 /usr/local/bin/openolat-* \
    && useradd --create-home openolat \
    && mkdir /opt/olatdata

COPY . /src
WORKDIR /src

RUN mvn -B -ntp -Ptomcat -DskipTests package

# The JUnit tests (-Dwith-postgresql) create and drop their own database "olattest" as postgres/postgres.
# Two test classes run here only to cache the test plugins for `mvn -o`; failures do not fail the build.
RUN service postgresql start \
    && runuser -u postgres -- psql -q -v ON_ERROR_STOP=1 \
         -c "ALTER USER postgres PASSWORD 'postgres'" \
         -c "CREATE USER openolat PASSWORD 'openolat'" \
         -c "CREATE DATABASE openolat OWNER openolat" \
    && (mvn -B -ntp -Ptomcat -Dwith-postgresql -Dtest=StringHelperTest,IdentityDAOTest \
          -Dsurefire.failIfNoSpecifiedTests=false test || echo "WARNING: tests failed") \
    && service postgresql stop

# First start: OpenOlat creates its database schema and the default administrator, so later starts are faster.
RUN openolat-start && openolat-stop
