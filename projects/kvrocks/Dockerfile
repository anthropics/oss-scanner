FROM golang:1.26-trixie

ARG BUILD_JOBS=8
ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local

RUN apt-get update && apt-get install -y --no-install-recommends \
      autoconf automake build-essential ca-certificates clang cmake curl \
      gdb git libssl-dev libtool ninja-build openssl pkg-config python3 \
      redis-tools \
    && rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN mkdir -p tests/gocase/tls/cert \
    && openssl req -x509 -newkey rsa:2048 -sha256 -nodes -days 3650 \
      -subj /CN=localhost -addext subjectAltName=DNS:localhost \
      -addext extendedKeyUsage=serverAuth,clientAuth \
      -keyout tests/gocase/tls/cert/server.key \
      -out tests/gocase/tls/cert/server.crt \
    && cp tests/gocase/tls/cert/server.crt tests/gocase/tls/cert/ca.crt

RUN python3 x.py build --ninja --compiler=clang --unittest -j "${BUILD_JOBS}" \
      -DCMAKE_BUILD_TYPE=RelWithDebInfo \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DCMAKE_C_FLAGS=-fno-omit-frame-pointer \
      -DCMAKE_CXX_FLAGS=-fno-omit-frame-pointer \
      -DCMAKE_EXE_LINKER_FLAGS=-latomic \
      -DENABLE_OPENSSL=ON -DPORTABLE=1

RUN cd tests/gocase && go mod download \
    && go test -run '^$' ./...

# These tests launch local Kvrocks processes and need no external services.
RUN timeout 300 python3 x.py test cpp \
    && cd tests/gocase \
    && mkdir -p workspace \
    && timeout 300 go test -count=1 -p 1 -parallel 2 -timeout 120s \
      ./unit/auth ./unit/namespace ./unit/scripting ./tls \
      -binPath=/src/build/kvrocks -cliPath=/usr/bin/redis-cli \
      -workspace=/src/tests/gocase/workspace -tlsEnable

# Offline: python3 x.py test cpp
# Offline: python3 x.py test go build -p 1 -parallel 2 -timeout 10m -tlsEnable
CMD ["bash"]
