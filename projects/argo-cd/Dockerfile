# Builds Argo CD from the checkout at /src and keeps everything needed to build and test it offline:
# the Go module cache, the UI's node_modules, and the helm, kustomize and git-lfs versions that Argo CD ships with.
FROM docker.io/library/golang:1.27-trixie

ENV DEBIAN_FRONTEND=noninteractive \
    CGO_ENABLED=0 \
    GODEBUG=tarinsecurepath=0,zipinsecurepath=0 \
    COREPACK_ENABLE_DOWNLOAD_PROMPT=0

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git gnupg gpg-agent openssh-client make unzip jq procps sudo \
    && rm -rf /var/lib/apt/lists/*

# Tests in reposerver/ and util/git create commits in temporary repositories and need a git identity.
RUN git config --system user.name "Argo CD Scanner" \
    && git config --system user.email "scanner@localhost"

# Node.js for the UI, from the official image (Argo CD's own Dockerfile builds the UI with Node 24).
COPY --from=docker.io/library/node:24-trixie /usr/local/bin/node /usr/local/bin/node
COPY --from=docker.io/library/node:24-trixie /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && ln -s ../lib/node_modules/corepack/dist/corepack.js /usr/local/bin/corepack \
    && node --version

COPY . /src
WORKDIR /src

# helm, kustomize and git-lfs at the versions pinned (and checksum-verified) in hack/tool-versions.sh.
# The repo-server runs these tools to render manifests. The installers call sudo, as in the release Dockerfile.
RUN BIN=/usr/local/bin ./hack/install.sh helm kustomize git-lfs \
    && git lfs install --skip-repo --system

# The repo-server calls these wrappers for GnuPG and commit signature verification; the release image puts them on PATH.
RUN install -m 0755 hack/gpg-wrapper.sh hack/git-verify-wrapper.sh /usr/local/bin/

# Go dependencies for both modules (the repository root and the nested gitops-engine module). If go.mod asks for a
# newer Go than this image has, the toolchain is downloaded here and stays in the module cache for offline use.
RUN go mod download && (cd gitops-engine && go mod download)

# Argo CD ships one multi-call binary that picks its component from its name, as in the release images.
RUN go build -o /usr/local/bin/argocd ./cmd \
    && for name in argocd-server argocd-repo-server argocd-application-controller argocd-applicationset-controller \
         argocd-cmp-server argocd-commit-server argocd-notifications argocd-dex argocd-git-ask-pass argocd-k8s-auth; do \
         ln -s argocd "/usr/local/bin/$name"; \
       done \
    && argocd version --client --short

# Compile every non-test package once so later builds and reproducers are fast.
RUN go build ./... && (cd gitops-engine && go build ./...)

# UI dependencies, so the UI can be built and tested offline (pnpm version comes from ui/package.json).
RUN cd ui && corepack enable && pnpm install --frozen-lockfile

# Baseline tests for the security-sensitive areas: auth/session/RBAC, the API server, and manifest generation.
# A failing test must not abort the build. The skipped tests expect permission errors, which root never gets.
RUN go test -short -p 4 -timeout 20m \
      -skip '^(TestDirectoryPermissionInitializer|TestInit)$|^Test_getPotentiallyValidManifests$/^unreadable_file_throws_error$' \
      ./util/session/... ./util/oidc/... ./util/rbac/... ./util/settings/... ./server/logout/... \
      ./server/application/... ./server/project/... ./reposerver/repository/... ./util/helm/... ./util/kustomize/... \
    || echo 'WARNING: baseline Go tests reported failures'

# Reproducers and patches must build with the network disabled.
ENV GOPROXY=off \
    GOSUMDB=off

CMD ["bash"]
