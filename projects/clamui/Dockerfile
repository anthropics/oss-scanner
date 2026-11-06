# The scanner uses the ClamUI checkout as the context, NOT this enrollment folder.
# Ubuntu 24.04 supplies GLib 2.80 and girepository-2.0 for current PyGObject.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_PYTHON_DOWNLOADS=never \
    HYPOTHESIS_PROFILE=ci \
    MPLBACKEND=Agg

RUN apt-get update && apt-get install -y --no-install-recommends \
        bash build-essential ca-certificates clang curl git pkg-config \
        python3 python3-dev python3-pip python3-venv \
        libgirepository-2.0-dev libcairo2-dev libjpeg-dev zlib1g-dev \
        gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-gdkpixbuf-2.0 \
        librsvg2-common adwaita-icon-theme fonts-dejavu-core \
        xvfb xauth dbus-x11 dbus-daemon util-linux \
        clamav clamav-daemon clamav-freshclam \
        pkexec polkitd gnupg dpkg-dev fakeroot gettext \
    && rm -rf /var/lib/apt/lists/*

# Keep build tooling out of the system Python installation.
RUN python3 -m venv /opt/uv \
    && /opt/uv/bin/python -m pip install --no-cache-dir uv==0.12.23 \
    && useradd --create-home --uid 10001 --shell /bin/bash clamui-test \
    && git config --system --add safe.directory /src

# Required scanner convention: keep the complete, editable checkout in /src.
COPY --chown=10001:10001 . /src
WORKDIR /src

# All Python runtime, test and wheel-build dependencies are fetched online here.
# Use the committed lock; never silently resolve different application dependencies.
RUN /opt/uv/bin/uv sync --locked --extra dev --python /usr/bin/python3 \
    && /opt/uv/bin/uv pip check --python /src/.venv/bin/python \
    && /opt/uv/bin/uv build --wheel --out-dir /opt/clamui-artifacts

ENV PATH="/src/.venv/bin:/opt/uv/bin:${PATH}"

# Exercise the project's actual helper packaging path without installing it.
RUN bash debian/build-privileged-helper-deb.sh /opt/clamui-artifacts

# Run normal application tests as an ordinary account even though the scanner
# itself opens a root shell. Forward every pytest argument without shell expansion.
RUN printf '%s\n' \
        '#!/bin/sh' \
        'set -eu' \
        'if [ "$(id -u)" -eq 0 ]; then' \
        '    exec runuser -u clamui-test -- "$0" "$@"' \
        'fi' \
        'cd /src' \
        'exec dbus-run-session -- xvfb-run -a /src/.venv/bin/python -m pytest --ignore=tests/e2e "$@"' \
        > /usr/local/bin/clamui-tests \
    && chmod 0755 /usr/local/bin/clamui-tests \
    && mkdir -p /opt/clamui-validation \
    && chown -R clamui-test:clamui-test /opt/clamui-artifacts

# Record the existing suite's baseline; failures stay visible and do not discard
# an otherwise useful audit image. A timeout is recorded as exit code 124.
RUN if timeout 600 clamui-tests -q > /opt/clamui-validation/pytest.log 2>&1; then \
        printf '0\n' > /opt/clamui-validation/pytest.exit-code; \
    else \
        result=$?; \
        printf '%s\n' "$result" > /opt/clamui-validation/pytest.exit-code; \
        printf 'WARNING: baseline pytest exited %s; inspect /opt/clamui-validation/pytest.log\n' "$result"; \
    fi \
    && tail -n 40 /opt/clamui-validation/pytest.log

# Analysis and repeat test runs must use installed dependencies, without downloads.
# Do not run freshclam here: unit/integration tests mock ClamAV subprocesses;
# production signatures, a live clamd, a desktop and Flatpak host are not provisioned.
ENV UV_OFFLINE=1
CMD ["bash"]
