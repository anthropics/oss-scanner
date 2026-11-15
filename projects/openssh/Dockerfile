FROM debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive \
    CC=clang
RUN apt-get update && apt-get install -y --no-install-recommends \
      clang make autoconf automake sudo \
      tmux putty-tools dropbear dropbear-bin net-tools \
      libc-dev libz-dev libssl-dev libpam-dev libkrb5-dev libedit-dev \
      libaudit-dev libselinux1-dev selinux-policy-dev \
      libfido2-dev libu2f-host-dev libcbor-dev \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/empty

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build the project as its maintainers build it, with debug info (-g) and frame pointers. A step that fails fails the
# build, and primary_contact gets the log.
RUN cd /src && autoreconf && mkdir build && cd build && mkdir default no-openssl kitchensink

# Build with default options.
RUN cd /src/build/default && ../../configure --with-privsep-user=nobody && \
    make regress-prep && make -j$(nproc) all regress-binaries

# Build without OpenSSL or zlib (minimal dependencies).
RUN cd /src/build/no-openssl && ../../configure --with-privsep-user=nobody \
    --without-openssl --without-zlib && \
    make regress-prep && make -j$(nproc) all regress-binaries

# Build with everything plus the kitchen sink (maximal dependencies).
# See .github/configs for suggestions.
RUN cd /src/build/kitchensink && ../../configure --with-privsep-user=nobody \
    --with-kerberos5 --with-libedit --with-pam \
    --with-security-key-builtin --with-selinux \
    --with-linux-memlock-onfault --with-audit=linux \
    --with-cflags="-DSK_DEBUG -DSANDBOX_SECCOMP_FILTER_DEBUG -DBROKEN_SNPRINTF" && \
    make regress-prep && make -j$(nproc) all regress-binaries

# Run the cheap tests so you know the image works, but do not let a
# failing test abort the build. Leave anything worth exercising (binaries,
# test drivers, examples) where threat_model.md says it is.
RUN cd /src/build/ && for i in default no-openssl kitchensink; do \
	(make -C$i t-exec LTESTS="connect proxy-connect" || \
	echo "WARNING: basic functionality failed for $i") \
    done
