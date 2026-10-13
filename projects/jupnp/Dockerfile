FROM eclipse-temurin:17-jdk-jammy

ENV MAVEN_OPTS="-Xmx2g -Dmaven.wagon.http.retryHandler.count=5 -Dmaven.wagon.httpconnectionManager.ttlSeconds=25"

COPY . /src
WORKDIR /src

RUN apt-get update && apt-get install -y --no-install-recommends unzip \
    && rm -rf /var/lib/apt/lists/*

RUN ./mvnw -B -ntp -U clean verify
