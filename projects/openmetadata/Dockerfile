# Build OpenMetadata for Anthropic's OSS Scanner.
# The scanner uses the repository root as the build context and audits /src offline.
#
# The JDK base and Maven pins match docker/olivaw/Dockerfile; bump them together.
FROM eclipse-temurin:21-jdk-jammy@sha256:dbfd085220ae632a0830166e443747d1ee89e9038d92e3b48c3e5e9d8292b9a7

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG MAVEN_VERSION=3.9.9
ARG MAVEN_SHA512=a555254d6b53d267965a3404ecb14e53c3827c09c3b94b5678835887ab404556bfaf78dcfe03ba76fa2508649dca8531c74bca4d5846513522404d48e8c4ac8b

ENV DEBIAN_FRONTEND=noninteractive \
    MAVEN_HOME=/opt/maven \
    PATH=/opt/maven/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git make \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN ln -s "${JAVA_HOME}/bin/java" /usr/bin/java

RUN curl -fsSL --retry 3 --retry-all-errors \
        "https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/apache-maven-${MAVEN_VERSION}-bin.tar.gz" \
        -o /tmp/maven.tar.gz \
    && echo "${MAVEN_SHA512}  /tmp/maven.tar.gz" | sha512sum --check --strict - \
    && mkdir -p "${MAVEN_HOME}" \
    && tar -xzf /tmp/maven.tar.gz -C "${MAVEN_HOME}" --strip-components=1 \
    && rm /tmp/maven.tar.gz \
    && mvn --version

# Scanner contract: the checkout lives inside the image, at /src.
COPY . /src
WORKDIR /src

RUN make install_antlr_cli

# Build and install all Maven modules, including their test classes.
RUN mvn -B -ntp -DskipTests install

# Run default unit tests in every module; report failures without stopping image setup.
RUN mvn -B -ntp --fail-never surefire:test
