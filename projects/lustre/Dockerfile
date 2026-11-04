# Lustre server + client build on Rocky Linux 10 (RHEL 10 is a primary Lustre server platform).
# ldiskfs patches the kernel's own ext4, so the build needs the kernel source (from the
# kernel SRPM) next to the kernel-devel objects. Kernel modules are compiled, not loaded:
# the sandbox has no Lustre-capable kernel, so the filesystem cannot be mounted here.
FROM quay.io/rockylinux/rockylinux:10

RUN dnf -y install dnf-plugins-core epel-release \
    && dnf config-manager --set-enabled crb \
    && dnf -y install \
        kernel-devel kernel-headers kernel-rpm-macros kernel-abi-stablelists \
        gcc gcc-c++ make autoconf automake libtool pkgconf-pkg-config flex bison \
        patch diffutils file which git rsync bc cpio xz \
        elfutils-libelf-devel elfutils-devel binutils-devel \
        libyaml-devel libnl3-devel libmount-devel libselinux-devel \
        openssl-devel krb5-devel keyutils-libs-devel libattr-devel libaio-devel \
        readline-devel zlib-ng-compat-devel json-c-devel libtirpc-devel libblkid-devel libuuid-devel \
        systemd-devel python3 python3-devel swig redhat-rpm-config checkpolicy policycoreutils \
        gdb strace \
    && dnf clean all

# The ext4 sources ldiskfs patches come from the SRPM of the installed kernel-devel.
RUN set -e; ver=$(rpm -q --qf '%{VERSION}-%{RELEASE}' kernel-devel); \
    cd /usr/src \
    && dnf -y download --source --enablerepo=baseos-source "kernel-$ver" \
    && rpm2cpio "kernel-$ver.src.rpm" | cpio -idm 'linux-*.tar.xz' \
    && tar xf linux-*.tar.xz \
    && rm -f linux-*.tar.xz "kernel-$ver.src.rpm" \
    && ln -s "/usr/src/linux-$ver" /usr/src/linux \
    && ln -s /usr/src/kernels/"$(ls /usr/src/kernels)" /usr/src/linux-obj

# mkfs.lustre and the ldiskfs utilities need Whamcloud's e2fsprogs (ext2fs >= 1.47.3-wc2).
RUN printf '[whamcloud-e2fsprogs]\nname=Whamcloud e2fsprogs\nbaseurl=https://downloads.whamcloud.com/public/e2fsprogs/latest/el10/\nenabled=1\ngpgcheck=0\n' \
        > /etc/yum.repos.d/whamcloud-e2fsprogs.repo \
    && dnf -y install e2fsprogs e2fsprogs-devel e2fsprogs-libs libcom_err libcom_err-devel libss \
    && dnf clean all

COPY . /src
WORKDIR /src

# Server with the ldiskfs backend, GSS/Kerberos, and the client; ZFS is left out
# (it needs a matching OpenZFS build). Debug info is on by default (-g -O2).
RUN sh autogen.sh \
    && ./configure \
        --with-linux=/usr/src/linux \
        --with-linux-obj=/usr/src/linux-obj \
        --enable-server --enable-ldiskfs --without-zfs \
        --enable-gss --disable-doc \
    && make -j"$(nproc)" \
    && make install

# wiretest checks the wire-protocol struct layout the userspace tools were built with.
RUN lustre/utils/wiretest && lctl --version && lnetctl --help >/dev/null
