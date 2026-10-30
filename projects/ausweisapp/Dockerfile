FROM alpine:3.24
RUN apk --no-cache upgrade -a && \
    apk --no-cache add patch cmake make ninja g++ pkgconf pcsc-lite-dev binutils-gold eudev-libs \
        llhttp-dev openssl-dev \
        qt6-qtbase-dev qt6-qtsvg-dev qt6-qtwebsockets-dev qt6-qttools-dev qt6-qtdeclarative-dev qt6-qtscxml-dev qt6-qtconnectivity-dev qt6-qtimageformats-dev qt6-qtimageformats

COPY README.rst /src/ausweisapp/
COPY LICENSE.txt/ /src/ausweisapp/
COPY LICENSE.officially.txt/ /src/ausweisapp/
COPY docs/ /src/ausweisapp/docs/
COPY CMakeLists.txt /src/ausweisapp/
COPY cmake/ /src/ausweisapp/cmake/
COPY resources/ /src/ausweisapp/resources/
COPY src/ /src/ausweisapp/src/
COPY test/ /src/ausweisapp/test/

RUN cmake /src/ausweisapp -B /build/app \
        -DBUILD_SHARED_LIBS=ON \
        -GNinja

RUN cmake --build /build/app

RUN ctest --test-dir /build/app --output-on-failure -j `nproc`
