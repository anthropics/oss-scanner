FROM eclipse-temurin:17-jdk-jammy
ENV DEBIAN_FRONTEND=noninteractive \
    MAVEN_OPTS="-Xmx1g -Dmaven.wagon.http.retryHandler.count=5 -Dmaven.wagon.httpconnectionManager.ttlSeconds=25"
RUN apt-get update && apt-get install -y --no-install-recommends maven ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

# Run the project tests but skip IPv6 multicast, which is unavailable in the scanner's isolated network.
RUN mvn -B test -Dtest='*,!JmDNSTest#testListMyServiceIPV6'
