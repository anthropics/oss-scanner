# OSS Scanner build of Open vSwitch (OVS).
#
# What is built:
#   /src   in-tree userspace build (autotools), compiled with debug info and frame
#          pointers. Produces libopenvswitch plus the daemons and utilities
#          (ovs-vswitchd, ovsdb-server, ovs-vsctl, ovs-ofctl, ovsdb-tool, ...).
#          `make check` works here (the testsuite is large; see the smoke test
#          at the end of this file for how to run it).
#
# DPDK is intentionally NOT enabled. DPDK is normally built from its own sources
# and vendored in, which would pull a large amount of DPDK-specific code into the
# scan surface and generate findings outside the scope of the OVS security team.
# This build therefore uses the native userspace datapath only (no --with-dpdk).
FROM docker.io/library/ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    CC=gcc \
    CXX=g++

# Build toolchain and OVS dependencies.
#   libssl-dev/openssl      - SSL/TLS support for OVSDB and OpenFlow connections
#   python3-sphinx          - manpage/documentation generation during the build
#   gcc g++ make            - compilers and build driver
#   autoconf automake libtool - autotools, driven by ./boot.sh
#   libunbound-dev          - enables the real DNS resolver (lib/dns-resolve.c, which
#                             parses DNS responses); without it OVS builds a no-op stub
#   procps nmap (ncat) iproute2 - runtime helpers the testsuite shells out to
#   libcap-ng-dev           - fine-grained capability (privilege drop) support
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates git pkg-config \
      gcc g++ make autoconf automake libtool \
      libssl-dev openssl \
      python3 python3-pip python3-sphinx \
      libcap-ng-dev \
      libunbound-dev \
      procps ncat iproute2 \
      gdb less \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Build OVS as its maintainers build it (autotools), with debug info (-g) and
# frame pointers so the scanner gets usable stack traces. A failing step fails
# the build, and primary_contact receives the log.
RUN ./boot.sh \
    && ./configure \
         --enable-ssl \
         CFLAGS="-g -O2 -fno-omit-frame-pointer" \
    && make -j"$(nproc)"

# Smoke test: confirm the built daemons and utilities run. The full testsuite is
# large and slow, so it is not run during the build; run it inside the image with:
#   cd /src && make check -j"$(nproc)" TESTSUITEFLAGS="-j$(nproc)"
# or a subset, e.g.:
#   cd /src && make check TESTSUITEFLAGS="ovs-vsctl"
# A failing smoke test must not abort the build.
RUN ( utilities/ovs-vsctl --version \
      && vswitchd/ovs-vswitchd --version \
      && ovsdb/ovsdb-server --version \
      && utilities/ovs-ofctl --version ) \
    || echo "WARNING: OVS smoke test reported failures"
