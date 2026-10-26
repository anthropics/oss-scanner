FROM maven:3.10.0-eclipse-temurin-17-noble

# Preserve the dependency cache for the scanner's later offline Maven runs.
ENV MAVEN_OPTS="-Dmaven.repo.local=/opt/maven-repository"

# The scanner requires the complete checkout, fixtures and build output at /src.
COPY . /src
WORKDIR /src

# Fetch dependencies by exercising the full reactor, including test providers.
# Javadocs use external links and are unnecessary for the security audit.
RUN mvn -B -ntp -Dmaven.javadoc.skip=true clean install

# Check that Maven can repeat the build without downloading dependencies.
# Repeat this command in the network-disabled shell opened by tools/check.
RUN mvn -B -ntp -o -Dmaven.javadoc.skip=true clean verify
