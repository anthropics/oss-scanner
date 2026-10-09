# Partial Linux audit environment. The macOS application and its Swift tests
# require AppKit and cannot be built here. Enrollment requires operator review
# of this limitation; this is not a substitute for the required native build.
FROM swift:6.0.3-noble
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git python3 clang libarchive-dev libarchive-tools \
      zip unzip xz-utils \
    && rm -rf /var/lib/apt/lists/*
COPY . /src
WORKDIR /src
# The C interoperability target is buildable without Apple frameworks.
RUN swift build --target CArchive
# Syntax parsing does not type-check or link AppKit code.
RUN find Sources/Foldera Tests/FolderaTests -name '*.swift' -print0 \
    | xargs -0 -n 1 swiftc -frontend -parse
CMD ["bash"]
