# Scilab (https://www.scilab.org): open-source numerical computation package and scientific
# programming language. Sources are a mix of C/C++/Java/Fortran and the Scilab language itself,
# one directory per feature under scilab/modules/ 
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive \
    LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8 \
    CC=gcc-12 \
    CXX=g++-12 \
    FC=gfortran-12 \
    F77=gfortran-12
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git rsync xz-utils zip unzip bzip2 gettext locales \
      gcc-12 g++-12 gfortran-12 make binutils libc-dev pkg-config \
      openjdk-21-jdk libgl1-mesa-dev \
      xvfb libxft2 libxtst6 libxi6 libgtk-3-0 libnspr4 libnss3 \
    && locale-gen en_US.UTF-8 fr_FR.UTF-8 ja_JP.UTF-8 pt_BR.UTF-8 ru_RU.UTF-8 zh_TW.UTF-8 \
    && update-locale \
    && rm -rf /var/lib/apt/lists/*
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src/scilab

# Third-party prerequisites: fetch and unpack them into the checkout, as the CI does before
# configuring. Anything the build or the tests need that is not a Debian package comes from here.
RUN curl -fsSL -o /tmp/prereq.tar.xz \
      "https://oos.eu-west-2.outscale.com/scilab-releases-dev/prerequirements/prerequirements-scilab-branch-main.bin.x86_64-linux-gnu.tar.xz" \
    && tar -xJf /tmp/prereq.tar.xz -C /src/scilab \
    && rm /tmp/prereq.tar.xz

# ant ships in the prerequisites tarball (java/ant is a symlink to the versioned directory)
ENV PATH=/src/scilab/java/ant/bin:$PATH

# Build
RUN ./configure \
    && make -j"$(nproc)" all

