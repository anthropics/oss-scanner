FROM ghcr.io/flathub-infra/flatpak-builder-lint@sha256:0eac22bc93dd78a01d168536ac7ac88dfe6562d28f33ae7ef7ee3da100d46e70

ENV PYTHONDONTWRITEBYTECODE=1

COPY . /src
WORKDIR /src
RUN mkdir -p /usr/local/bin

RUN cp /app/lib/python3.14/site-packages/flatpak_builder_lint/staticfiles/flathub-*.summary \
        /src/flatpak_builder_lint/staticfiles/ \
    && uv venv --python /usr/sbin/python3 --system-site-packages /opt/venv \
    && uv pip install --python /opt/venv/bin/python pytest pytest-xdist

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONPATH="/src:${PYTHONPATH}"

RUN python -m pytest -q

CMD ["/bin/bash"]
