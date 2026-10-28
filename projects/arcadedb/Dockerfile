FROM eclipse-temurin:21-jdk-jammy
ENV DEBIAN_FRONTEND=noninteractive \
    MAVEN_OPTS="-Xmx3g"
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git curl unzip \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build every server-side module with debug info and keep the test classes and test dependencies in ~/.m2, so the
# offline audit can compile and run tests. Studio (webapp), packaging and the e2e/load-test modules are skipped: Studio
# sources stay readable under /src/studio, they just are not built.
RUN ./mvnw -B -q install -DskipTests -Dmaven.javadoc.skip=true \
      -pl '!studio,!package,!coverage,!e2e,!e2e-ha,!load-tests,!gremlin-consumer-it' -am

# Run a few fast engine tests online, so Surefire's JUnit provider lands in ~/.m2 and the offline audit can run tests too,
# then once more with Maven offline to prove it. A failing test must not abort the build.
RUN ./mvnw -B test -pl engine -Dtest='SelectStatementExecutionTest,TransactionIsolationTest' \
    || echo "WARNING: sample tests reported failures"
RUN ./mvnw -B -o test -pl engine -Dtest='SelectStatementExecutionTest' \
    || echo "WARNING: offline sample tests reported failures"
