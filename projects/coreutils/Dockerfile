FROM registry.fedoraproject.org/fedora:latest

# Build dependencies
# glibc-gconv-extra is acually a tarball testing dep which will
# eventually get to fedora latest
RUN dnf install -y --setopt=install_weak_deps=False dnf5-plugins \
    && dnf builddep -y coreutils \
    && dnf install -y --setopt=install_weak_deps=False \
        git gperf bison m4 patch glibc-gconv-extra \
    && dnf clean all

COPY . /src
WORKDIR /src

# Source dependencies
# Note texi2pdf is only required when making doc releases,
# so define it to makeinfo which has a much smaller set of dependencies

# Note change the gnulib submodule default so we pull everything from github
# Also this results in a shallow clone which is much faster.
# Remove GNULIB_REVISION to use the latest gnulib
RUN rm .gitmodules; rmdir gnulib
RUN GNULIB_URL=https://github.com/coreutils/gnulib.git \
    GNULIB_REVISION=$(git rev-parse HEAD:gnulib) \
    WGET=true TEXI2PDF=makeinfo ./bootstrap --skip-po

# Build
RUN FORCE_UNSAFE_CONFIGURE=1 ./configure --quiet && make WERROR_CFLAGS= -s -j"$(nproc)"

# Test
RUN make -j"$(nproc)" check || echo 'WARNING: test failures'
