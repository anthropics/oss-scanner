# Scanner image for https://github.com/getprobo/probo (main).
#
# The audit runs offline, so this build fetches every Go module and npm package, builds the three web apps the server
# embeds (console, compliance portal, employee portal) and the email templates, generates the GraphQL and MCP code,
# then builds every binary and compiles every Go test, the way .github/workflows/make.yaml does. threat_model.md, next
# to this file, says what each binary is.

# The Go release the repository's CI uses (go.mod and .github/actions/setup). The image has git and gcc, which the race
# detector needs.
FROM golang:1.27-bookworm
ENV DEBIAN_FRONTEND=noninteractive
# curl to speak to a running probod, openssl for `make dev-config`, xz to unpack Node. Packages are fetched over HTTPS.
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends curl openssl xz-utils \
    && rm -rf /var/lib/apt/lists/*

# The Node release in .nvmrc and the npm major CI installs on top of it.
ARG NODE_VERSION=24.19.0
RUN case "$(dpkg --print-architecture)" in amd64) arch=x64 ;; arm64) arch=arm64 ;; *) exit 1 ;; esac \
    && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-${arch}.tar.xz" \
       | tar -xJ -C /usr/local --strip-components=1 \
    && npm install -g npm@^12.0.2

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

# Every Go module and npm package the build and the tests depend on.
RUN go mod download && npm ci

# The email templates, the Relay artifacts, the three web apps, the generated GraphQL/MCP servers, then every binary
# (probod, prb, probod-bootstrap, proboctl, probo-agent) into bin/. WITH_APPS=1 embeds the real web apps instead of
# placeholders. A step that fails fails the build, and primary_contact gets the log.
RUN make WITH_APPS=1 build \
    && CGO_ENABLED=1 go test -race -exec /bin/true ./...

# Everything is fetched. From here on the go command must not try to reach a proxy or download a toolchain.
ENV GOPROXY=off \
    GOTOOLCHAIN=local
