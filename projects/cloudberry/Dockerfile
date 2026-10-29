# Build Apache Cloudberry the way its own CI does: on the project's prebuilt
# build image (which already carries the gpadmin user, passwordless sudo, and
# every build dependency) using the repository's own configure/build scripts.
#
# The scanner supplies the apache/cloudberry checkout as the build context, so
# `COPY . /src` places the source — including devops/build/automation/... — in
# the image. Network is available during this build and removed afterwards, so
# everything the audit needs is fetched and compiled here.
FROM apache/incubator-cloudberry:cbdb-build-ubuntu24.04-latest

# Build with debug symbols and assertions (ENABLE_DEBUG=true), matching what we
# want the scanner to analyse: frame pointers and -g for good reproducers.
ENV SRC_DIR=/src \
    BUILD_DESTINATION=/usr/local/cloudberry-db \
    ENABLE_DEBUG=true

# The checkout lives inside the image at /src, owned by the build user.
COPY . /src
RUN chown -R gpadmin:gpadmin /src

WORKDIR /src

# Configure. The project's script runs ./configure with the full production
# feature set (orca, pax, gpcloud, gssapi, ldap, openssl, libxml, ...). A
# failure here fails the build, and primary_contact receives the log.
RUN chmod +x devops/build/automation/cloudberry/scripts/*.sh \
    && su - gpadmin -c "cd ${SRC_DIR} && SRC_DIR=${SRC_DIR} ENABLE_DEBUG=${ENABLE_DEBUG} BUILD_DESTINATION=${BUILD_DESTINATION} ${SRC_DIR}/devops/build/automation/cloudberry/scripts/configure-cloudberry.sh"

# Compile and install into BUILD_DESTINATION.
RUN su - gpadmin -c "cd ${SRC_DIR} && SRC_DIR=${SRC_DIR} BUILD_DESTINATION=${BUILD_DESTINATION} ${SRC_DIR}/devops/build/automation/cloudberry/scripts/build-cloudberry.sh"

# Smoke-test with the unit tests (no cluster needed). Do not let a failing test
# abort the build — the binaries and source are what the scanner analyses.
RUN su - gpadmin -c "cd ${SRC_DIR} && SRC_DIR=${SRC_DIR} BUILD_DESTINATION=${BUILD_DESTINATION} ${SRC_DIR}/devops/build/automation/cloudberry/scripts/unittest-cloudberry.sh" \
    || echo "WARNING: unit tests reported failures (non-fatal for the scan image)"
