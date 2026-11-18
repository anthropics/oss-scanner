# Threat model

## What kaniko does and where untrusted input enters

kaniko builds container images from a Dockerfile inside a container, without a daemon and without privileges. The executor runs as root inside its own container and treats that container's root filesystem as the build filesystem: it unpacks base image layers onto `/`, runs `RUN` commands directly on it, and snapshots changes into new layers. It is used in CI systems (GitLab CI, Tekton, Kubernetes jobs) to build images from repositories that may contain contributions from untrusted people.

kaniko is not a sandbox. Whoever controls the Dockerfile controls `RUN` and therefore has code execution in the build container. The security goals below protect the build from inputs that are untrusted even when the Dockerfile is trusted, and protect what leaves the build container.

Untrusted inputs:

- Base images and `COPY --from=<image>` images pulled from registries: manifests, indexes, configs and layer tarballs. A registry or a base image author is not trusted.
- The build context: a local directory, or a tarball fetched from S3, GCS, Azure Blob, HTTPS or git (`pkg/buildcontext`). Files, symlinks and hardlinks in the context are attacker controlled, for example in a merge request build with a maintainer-owned Dockerfile.
- Remote cache images (`--cache-repo`) and cached base images in `--cache-dir` (written by the warmer).
- Registry responses during push and pull, including auth challenges and redirects.

Security goals:

- Layer extraction never writes outside the build root or into ignored paths: `/kaniko` (`KANIKO_DIR`), mounted filesystems from `/proc/self/mountinfo` (service account tokens, mounted secrets), and paths passed with `--ignore-path`.
- `COPY` and `ADD` from the build context never read files outside the context, for example through symlinks or `..` paths, and never pick up files from `/kaniko`.
- Credentials (`/kaniko/.docker/config.json`, credential helper output, `RUN --mount=type=secret` contents) never end up in pushed image layers, the image config, cache layers or logs.
- A cache entry is only reused for a build step whose inputs match its key.

## Components that matter most / least

Most important:

- `pkg/util/fs_util.go` and `pkg/util/tar_util.go`: layer and tar extraction, symlink and hardlink handling, ignore list.
- `pkg/commands/copy.go`, `pkg/commands/add.go` and `pkg/util/command_util.go`: resolving `COPY`/`ADD` sources and destinations.
- `pkg/buildcontext`: fetching and unpacking remote build contexts.
- `pkg/snapshot`: deciding which files go into a layer.
- `pkg/executor` and `pkg/cache`: cache key computation and cache reuse.
- `pkg/creds` and `pkg/mounts`: credential and secret handling.

Out of scope:

- `vendor/`: third-party code. Report issues there only when kaniko's use of it is what makes them exploitable.
- `integration/`, `golden/`, `hack/`, `scripts/`: tests and tooling.

## How to exercise it

The executor rewrites the root filesystem of the machine it runs on. Do not run `out/executor` in this image except with `--dryrun`, which only renders the build plan. To reproduce a finding, write a Go test next to the affected package that calls the function directly on files in a temporary directory, for example tar extraction in `pkg/util`. Existing `*_test.go` files show how to build layers and contexts in memory.

There is no network and no registry in this image.

## How you rate severity

- Critical: a base image, build context or cache entry writes outside the build root into `/kaniko`, a mounted secret path or the executor itself, or causes credentials to be pushed in an image or cache layer.
- High: a build context reads files outside the context into an image layer. Cache poisoning where an entry is reused for different inputs.
- Medium: credentials or secret contents written to logs.
- Low: denial of service through crafted images or contexts (memory, disk, decompression bombs, hangs).

## Anything to leave alone

- Anything that requires control of the Dockerfile. `RUN` already gives code execution in the build container.
- The lack of isolation between `RUN` and the executor. kaniko runs unprivileged by design and does not use namespaces, chroot or mounts. Running kaniko outside a dedicated container is unsupported.
- Behaviour that matches the Dockerfile reference, even where BuildKit behaves differently.
