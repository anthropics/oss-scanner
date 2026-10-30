# Sparrow Wallet (https://github.com/sparrowwallet/sparrow), a desktop Bitcoin wallet.
#
# Builds Sparrow and its drongo and lark submodules with Gradle and runs their unit tests once, so that the wrapper's
# Gradle distribution and every dependency are cached in the image for the offline scan that follows.
FROM eclipse-temurin:25.0.5_8-jdk-noble
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    GRADLE_USER_HOME=/opt/gradle-home \
    JDK_JAVAC_OPTIONS=-Xlint:-module
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# The checkout arrives without submodules. Their URLs in .gitmodules are relative to origin, which resolves to github.com/sparrowwallet.
RUN git submodule update --init --recursive

# Compile the main and test sources of all three projects, fetching the Gradle distribution and every dependency.
RUN ./gradlew --no-daemon --console=plain assemble testClasses

# Run the unit tests so the test runtime dependencies are cached too. A failing test does not abort the build.
RUN ./gradlew --no-daemon --console=plain --continue test || echo "WARNING: the unit tests reported failures"
