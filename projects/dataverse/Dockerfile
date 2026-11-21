FROM maven:3.9-eclipse-temurin-21

WORKDIR /src
COPY . /src

RUN mvn --batch-mode --no-transfer-progress \
    -DskipIntegrationTests=true \
    package