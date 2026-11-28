FROM fedora:44

# Match the Fedora dependencies in scripts/gen_dockerfiles.py, including TPM
# and SELinux support.
RUN dnf -y update && dnf -y install \
      git curl wget make pkg-config jq ca-certificates libtool autoconf gettext \
      checkpolicy policycoreutils python3 systemd authselect rpm-build \
      @development-tools gcc gcc-c++ openssl-devel dbus-devel krb5-devel \
      pam-devel libcap-devel libudev-devel cmake tpm2-tss-devel clang \
      pcre2-devel sqlite-devel libunistring-devel policycoreutils-devel \
      selinux-policy-targeted \
    && dnf clean all

ENV PATH="/root/.cargo/bin:${PATH}"
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs -o /tmp/rustup-init.sh \
    && sh /tmp/rustup-init.sh -y --profile minimal \
    && rm /tmp/rustup-init.sh

# The scanner supplies the Himmelblau checkout as the build context.
COPY . /src
WORKDIR /src

ARG CARGO_BUILD_JOBS=4
ENV RUSTFLAGS="-C force-frame-pointers=yes" \
    CARGO_PROFILE_RELEASE_DEBUG=2 \
    CARGO_PROFILE_RELEASE_STRIP=none

# Use the Fedora package build, retaining symbols for debugging. Keep Cargo's
# downloaded dependencies and compiled test drivers available for offline use.
RUN python3 src/common/scripts/gen_param_code.py --gen-man --man-output man/man5/himmelblau.conf.5 \
    && make rpm-servicefiles \
    && cargo build --locked --release --features tpm \
    && cargo test --locked --release --features tpm --no-run \
    && python3 scripts/test_hsm_pin_init.py

ENV CARGO_NET_OFFLINE=true
CMD ["/bin/bash"]
