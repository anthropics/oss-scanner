# Based on https://github.com/gnu-gettext/ci-check/

FROM ghcr.io/gnu-gettext/build-images/from-ubuntu24.04:latest

# scanner contract: the checkout (from the URL in project.yaml) lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN git config --global url.git://git.git.savannah.gnu.org/.insteadOf git://git.savannah.gnu.org/ \
    && git config --global url.https://https.git.savannah.gnu.org/git/.insteadOf https://git.savannah.gnu.org/git/ \
    && git config --global url.https://github.com/coreutils/gnulib.git.insteadOf git://git.savannah.gnu.org/gnulib.git \
    && git config --global url.https://github.com/coreutils/gnulib.git.insteadOf https://git.savannah.gnu.org/git/gnulib.git \
    && git clone --depth 1 https://git.savannah.gnu.org/git/gnulib.git \
    && export GNULIB_SRCDIR=`pwd`/gnulib \
    && rm -f .gitmodules \
    && ./autopull.sh \
    && date --utc --iso-8601 > .tarball-version \
    && ./autogen.sh

# Configure
RUN ./configure --config-cache --disable-shared --with-included-libunistring CPPFLAGS="-Wall"

# Build
RUN make

# Test. The autopoint-3 test may fail.
RUN make check || echo "WARNING: there were test failures"
