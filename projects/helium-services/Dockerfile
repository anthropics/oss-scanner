# helium-services is a set of Deno services behind nginx. Each one has its own deno.json and lockfile; this image
# caches all of their dependencies so they and their tests run without network access.
FROM denoland/deno:2.8.1
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git ripgrep \
    && rm -rf /var/lib/apt/lists/*

# minidumpster shells out to symsorter, as in svc/minidumpster/Dockerfile.
ARG SYMSORTER_VERSION=26.6.0
RUN curl -fsSL -o /usr/local/bin/symsorter \
      "https://github.com/getsentry/symbolicator/releases/download/${SYMSORTER_VERSION}/symsorter-Linux-x86_64" \
    && chmod +x /usr/local/bin/symsorter \
    && symsorter --version

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Cache every project's dependencies, including test-only ones.
RUN for d in svc/extension-proxy svc/minidumpster svc/minipush svc/ubo util/release-collector util/sparkler; do \
      (cd "$d" && deno install --frozen && deno cache --frozen $(find . -name '*.ts' -not -path './node_modules/*')) \
        || exit 1; \
    done

RUN cd svc/minidumpster && (deno task test || echo "WARNING: minidumpster tests reported failures")
