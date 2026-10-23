# OSS Scanner build for Tesseract (https://github.com/tesseract-ocr/tesseract).
#
# Tesseract is the open-source OCR engine. This Dockerfile builds it the way upstream CI does with
# CMake (Ninja, shared libraries): libtesseract, the `tesseract` CLI and the training tools, with
# debug info and frame pointers so that memory errors give useful backtraces.
#
# The scanner clones the repository without its submodules and removes the network after this build,
# so the language models (needed to run the engine offline) are fetched here:
#
#   /src           the checkout, built in-tree (build/) and installed to /usr/local
#   /opt/tessdata  the eng and osd language models (TESSDATA_PREFIX is set to it)
#
# Nothing else is fetched. The OSS-Fuzz fuzzer source (unittest/fuzzers/fuzzer-api.cpp) is part of
# the main checkout, so it is already under /src; the only submodules (the tesseract-ocr/test
# regression corpus and the bundled GoogleTest) are intentionally left unfetched.
FROM docker.io/library/debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive \
    CXX=clang++ \
    TESSDATA_PREFIX=/opt/tessdata

# Build dependencies. Leptonica is the one hard runtime dependency; ICU and the Pango stack are
# required by the training tools. All come from the distribution, like a normal maintainer build.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl build-essential clang cmake ninja-build pkg-config git python3 \
      libleptonica-dev libtiff-dev libarchive-dev libcurl4-openssl-dev \
      libicu-dev libpango1.0-dev libcairo2-dev libfontconfig1-dev \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the project as its maintainers build it, with debug info (-g) and frame pointers. A step that
# fails fails the build, and primary_contact gets the log.
RUN cmake -S /src -B /src/build -G Ninja \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_CXX_FLAGS="-fno-omit-frame-pointer" \
    && cmake --build /src/build -j"$(nproc)" \
    && cmake --install /src/build

# Language models for running the engine. The in-tree tessdata/ holds only config files; the models
# are the "fast" (LSTM-only) versions, as used by most consumers.
RUN mkdir -p /opt/tessdata \
    && curl -fsSL -o /opt/tessdata/eng.traineddata  https://github.com/tesseract-ocr/tessdata_fast/raw/main/eng.traineddata \
    && curl -fsSL -o /opt/tessdata/osd.traineddata  https://github.com/tesseract-ocr/tessdata_fast/raw/main/osd.traineddata

# Smoke test: the CLI reports its version and actually OCRs a known image. Failures abort the build.
RUN curl -fsSL -o /tmp/phototest.tif https://raw.githubusercontent.com/tesseract-ocr/test/main/testing/phototest.tif \
    && tesseract --version \
    && tesseract /tmp/phototest.tif /tmp/phototest -l eng \
    && grep -q "This is a lot of 12 point text" /tmp/phototest.txt \
    && rm -f /tmp/phototest.tif /tmp/phototest.txt
