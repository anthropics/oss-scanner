# KubeVela build for the OSS Scanner.
# The scanner supplies the kubevela checkout as the build context. Network is available during this build
# and removed afterwards, so the Go toolchain, module cache, envtest binaries and test caches are all
# fetched here and kept in the image.
# Go version follows the `go` directive in kubevela's go.mod on master (1.27.x at enrolment time).
FROM golang:1.27-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    GOTOOLCHAIN=local \
    CGO_ENABLED=0

RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl git make jq procps \
    && rm -rf /var/lib/apt/lists/*

# scanner contract: the checkout lives inside the image, at /src
COPY . /src
WORKDIR /src

RUN go mod download

# Build the three binaries the project ships: the controller, the CLI and the kubectl plugin.
RUN go build -o /usr/local/bin/manager ./cmd/core \
    && go build -o /usr/local/bin/vela ./references/cmd/cli \
    && go build -o /usr/local/bin/kubectl-vela ./cmd/plugin

# Unit tests run a real kube-apiserver and etcd through controller-runtime envtest. Fetch those binaries now
# so the suite works offline. The release branch matches the controller-runtime version in go.mod (v0.25.x);
# the Kubernetes version matches ENVTEST_K8S_VERSION in makefiles/dependency.mk (1.37.0).
RUN GOBIN=/usr/local/bin go install sigs.k8s.io/controller-runtime/tools/setup-envtest@release-0.25 \
    && setup-envtest use 1.37.0 --bin-dir /opt/envtest -p path \
    && ln -s "$(setup-envtest use 1.37.0 --bin-dir /opt/envtest -p path)" /opt/kubebuilder-assets
ENV KUBEBUILDER_ASSETS=/opt/kubebuilder-assets

# The scanner's analysis container has no network interface and therefore no default route. kube-apiserver
# treats envtest's loopback --bind-address as unusable and tries to pick an advertise address from the routing
# table, then exits with "Unable to find suitable network address". Every envtest-based suite dies on that.
# Wrap the binary so --advertise-address=127.0.0.1 is always present; the tests themselves never set it.
# A loopback advertise address is refused by the endpoint reconciler ("may not be in the loopback range"), and
# envtest has no use for the kubernetes Service endpoints it publishes, so the reconciler is turned off too.
RUN mv /opt/kubebuilder-assets/kube-apiserver /opt/kubebuilder-assets/kube-apiserver.real \
    && printf '#!/bin/sh\nexec "$(dirname "$0")/kube-apiserver.real" --advertise-address=127.0.0.1 --endpoint-reconciler-type=none "$@"\n' \
         > /opt/kubebuilder-assets/kube-apiserver \
    && chmod +x /opt/kubebuilder-assets/kube-apiserver

# The shared client singletons resolve their REST config with controller-runtime's GetConfigOrDie, which calls
# os.Exit(1) through a sink-less logger when no kubeconfig exists at all. Several unit tests reach that path
# through the CueX default compiler and the whole test binary vanishes with no message. A kubeconfig only has
# to be resolvable, not reachable: point one at a closed port so the failure becomes an ordinary logged error.
RUN mkdir -p /root/.kube \
    && printf 'apiVersion: v1\nkind: Config\nclusters: [{name: none, cluster: {server: "https://127.0.0.1:1"}}]\ncontexts: [{name: none, context: {cluster: none, user: none}}]\nusers: [{name: none, user: {token: none}}]\ncurrent-context: none\n' \
         > /root/.kube/config

# These tests can never pass in this environment and would only send the scanner chasing noise:
#   TestGenSdk and TestNewDefinitionGenAPICommand run the OpenAPI generator through `docker`; none in the image.
#   TestAuthn, TestImageRegistry, TestHelmRepository, TestHelm, TestLoadRepo, TestHTTPGetKubernetesObjects,
#   TestCueXEval and TestGenerateTerraformCapabilityProperties reach registries, Helm repositories, cuelang.org
#   or GitHub over the network.
# Three specs inside the TestCli Ginkgo suite (addon status and listing against the public registry) also need
# the network. They are left running and listed in threat_model.md, because skipping TestCli would drop the
# whole CLI suite and Ginkgo's own skip flag cannot be passed through GOFLAGS.
# GOFLAGS applies to every `go test`, including the ones the scanner runs later; `go build` ignores -skip.
ENV GOFLAGS="-skip=^(TestGenSdk|TestNewDefinitionGenAPICommand|TestAuthn|TestImageRegistry|TestHelmRepository|TestHelm|TestLoadRepo|TestHTTPGetKubernetesObjects|TestCueXEval|TestGenerateTerraformCapabilityProperties)$"

# Run the unit tests the same way `make unit-test-core` does, so the build and test caches are warm offline.
# A failing baseline test must not abort the image build; the scanner still needs the environment.
RUN go test -timeout 30m $(go list ./pkg/... ./cmd/... ./apis/... | grep -v apiserver | grep -v applicationconfiguration) \
    || echo "WARNING: core unit tests reported failures"
RUN go test -timeout 20m $(go list ./references/... | grep -v apiserver) \
    || echo "WARNING: CLI unit tests reported failures"

# New reproducers and patches must also build with the network disabled.
ENV GOPROXY=off \
    GOSUMDB=off

CMD ["bash"]
