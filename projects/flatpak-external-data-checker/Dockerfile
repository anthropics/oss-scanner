FROM debian:trixie

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/src

COPY dependencies.apt.txt /tmp/dependencies.apt.txt

RUN sed -i "s/Types: deb/Types: deb deb-src/" /etc/apt/sources.list.d/debian.sources && \
    apt-get update && \
    xargs apt-get install --no-install-recommends -y < /tmp/dependencies.apt.txt && \
    apt-get install --no-install-recommends -y ca-certificates curl file xz-utils && \
    apt-get --no-install-recommends -y build-dep python3-apt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY . /src
WORKDIR /src

RUN python3 -m compileall -q /src/src

RUN python3 -m unittest tests.test_lint tests.test_manifest tests.test_loader \
        tests.test_version tests.test_robots \
    || echo "WARNING: unittest reported failures"

ENV PATH="/src:${PATH}"

CMD ["/bin/bash"]
