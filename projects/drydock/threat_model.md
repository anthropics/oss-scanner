# Drydock: threat model and severity guide for the scanner

Drydock is a Docker container update manager. It watches the containers on a Docker host, asks image registries
whether newer tags or digests exist, and then sends notifications or replaces the container with the newer image. It
ships as one container image, built from the repository-root `Dockerfile`, that holds the compiled backend (`app/`,
TypeScript on Node 24, Express) and the built dashboard (`ui/`, Vue 3). A normal deployment mounts the Docker socket,
or a socket proxy, into it. Docker socket access is root on the host, so a flaw that lets an outsider steer Drydock
usually hands over the host.

The project's own statement of its security goals is `/src/SECURITY-ASSURANCE.md`. It has a table of which outbound
request controls exist on which path, and which don't. `/src/content/docs/current/configuration/hooks/index.mdx`
documents the hook trust model. Read both before rating a finding.

## Who is trusted

- The operator, and everything the operator supplies: `DD_*` environment variables, mounted secret files, mounted
  compose files and certificates. All configuration comes from the environment.
- Anyone who can create containers on a watched Docker daemon. They already hold the socket. Labels set when a
  container is created (`docker run --label`, Compose `labels:`) are operator input.
- Every authenticated dashboard or API user. There are no roles: anyone who can log in can update, start, stop and roll
  back containers (see the note in `app/api/container-actions.ts`).

## Where untrusted input enters

- Network clients without credentials. These routes are reachable before session authentication: `/health`,
  `/auth/login`, `/auth/status`, the OIDC pair `/auth/oidc/<name>/redirect` and `/auth/oidc/<name>/cb`,
  `/api/v1/openapi.json`, `/api/v1/webhook/*` (bearer token), `/api/v1/webhooks/registry` (HMAC signature),
  `/api/v1/self-update/<id>/status` (the operation id is the capability), `/api/v1/internal/self-update/finalize`
  (loopback only, plus a per-operation secret), `/metrics` (bearer token or session), and the WebSocket upgrades
  `/api/v1/portwing/ws` (Ed25519 hello frame) and `/api/v1/log/stream` (session and origin check). The route order is
  in `app/api/api.ts` and `app/api/index.ts`. Everything else under `/api/v1` sits behind `requireAuthentication` and a
  same-origin check for mutations (`app/api/csrf.ts`).
- A hostile web page in the browser of a logged-in user: cross-site requests, cross-origin WebSocket upgrades, and
  anything that turns stored data into script.
- Registries. Tag lists, manifests, digests, error bodies, redirects and `WWW-Authenticate` challenges all come from
  the registry, including the token endpoint a challenge names.
- Image publishers. Docker copies an image's `LABEL`s into every container created from it, so any `dd.*` label can
  come from whoever published the image rather than from the operator. So can the OCI labels Drydock reads for
  release notes (`org.opencontainers.image.source`, `org.opencontainers.image.url`), along with image names and tags.
  Only `dd.hook.*` labels get a provenance check today.
- Remote agents. A controller connects out to agents (`DD_AGENT_<name>_*`, shared secret or Ed25519 request signing),
  and edge agents dial in over the WebSocket above. An agent is trusted to manage its own host. The container records,
  events and Docker API responses it sends must not let it run code on the controller, read the controller's secrets,
  or act on another agent's host.
- Other remote services Drydock calls: notification targets, the GitHub and Docker Hub APIs used for release notes,
  and the icon CDNs behind `/api/v1/icons`. Their responses, redirects and sizes are untrusted.
- Container output shown in the dashboard: container logs, and Trivy results about third-party images.

## Components that matter most

- Authentication and sessions: `app/api/auth*.ts`, `app/api/session-cookie.ts`, `app/api/csrf.ts`,
  `app/authentications/providers/` (basic with argon2id hashes, OIDC, anonymous). With no provider configured,
  Drydock registers no strategy and rejects protected requests unless `DD_ANONYMOUS_AUTH_CONFIRM=true` is set. A way
  around that is an authentication bypass.
- Webhooks: `app/api/webhook.ts` and `app/api/webhooks/` (signature check, one payload parser per registry). A webhook
  can start a watch or an update.
- Lifecycle hooks: `app/triggers/hooks/HookRunner.ts` and `app/triggers/providers/docker/HookExecutor.ts`. With
  `DD_HOOKS_ENABLED=true`, the `dd.hook.pre` and `dd.hook.post` labels run through `/bin/sh -c` inside the Drydock
  container. The defenses are a command grammar check, the optional `DD_HOOKS_ALLOWED_COMMANDS` list, sanitized
  `DD_*` hook environment values (image name, tag and digest are registry-controlled), and the provenance check that
  ignores hook labels baked into the image unless `DD_HOOKS_ALLOW_IMAGE_LABELS=true`. A bypass of any of these is
  command execution next to the Docker socket.
- The command action: `app/triggers/providers/command/Command.ts`. The command is the operator's, but container and
  image values reach it as environment variables.
- Container recreation: `app/triggers/providers/docker/` (spec cloning in `ContainerRuntimeConfigManager.ts`, the
  update and rollback executors, self-update) and `app/triggers/providers/dockercompose/`, which rewrites compose
  files it finds through `com.docker.compose.*` labels. Look for image-supplied or registry-supplied values that
  change what the new container runs, mounts or carries as labels, or which file gets written.
- Registry clients: `app/registries/` (`Registry.ts`, `BaseRegistry.ts`, `www-authenticate.ts`, `providers/`). They
  hold operator credentials and send them as Basic or Bearer headers. Look for credentials going to a host the
  operator didn't configure: challenge realms, redirects, the `dd.registry.lookup.image` label, host matching.
- Agents: `app/agent/` (client, agent-mode API, edge adapter, Docker bridge), `app/api/portwing-ws.ts`,
  `app/api/portwing.ts`.
- Image scanning: `app/security/` runs Trivy and cosign as child processes, with image references as arguments and
  registry credentials in the environment.
- Outbound fetches that image labels influence: `app/release-notes/` and `app/api/icons/` (which also sanitizes
  SVG).
- Real-time channels: `app/api/sse*.ts`, `app/api/log-stream.ts`, `app/api/ws-upgrade-utils.ts`.
- Notification templates: `app/triggers/providers/trigger-expression-parser.ts` and `Trigger.ts` evaluate
  operator-written templates against container data.
- Regular expressions from labels (`dd.tag.include`, `dd.tag.exclude`, `dd.tag.transform`) are compiled with re2js in
  `app/tag/` and `app/watchers/providers/docker/`. A label-supplied pattern reaching a native `RegExp` is a bug.
- State and secrets: `app/store/` (LokiJS, JSON files under `/store` by default: `dd.json` holds state and the
  generated session secret, `dd-sessions.json` holds sessions), redaction in `app/debug/` and `app/log/`.
- The dashboard: `ui/src/`. Vue escapes text and nothing uses `v-html` today, so look at `:href` and `src` bindings fed
  by labels, registries and release notes, and at the service worker.
- Also shipped: `healthcheck.c` (the image's static health probe), `Docker.entrypoint.sh` (the privilege drop), and
  the release pipeline in `.github/workflows/`, which builds and signs what users pull.

Lower priority: `scripts/` (maintainer tooling), and the 23 registry and 20 trigger providers beyond their shared base
classes.

## How to exercise it

Everything is built in `/src`. The scan image has no Docker daemon, no Trivy and no cosign.

    cd /src/app && npx vitest run                    # whole backend suite; runs files one at a time
    cd /src/app && npx vitest run triggers/hooks     # one area
    cd /src/app && npx vitest run .fuzz.test.ts      # the fast-check property tests
    cd /src/ui  && npx vitest run                    # dashboard suite (jsdom)

Neither suite needs a network or a Docker daemon. Both workspaces gate on 100% coverage. In this image the usual
commands (`npm test` in `app/`, `npm run test:unit` in `ui/`) report just under 100% on an untouched tree, for two
reasons that have nothing to do with your change. Use these instead, which report 100%:

    cd /src/app && env -u HOSTNAME npm test
    cd /src/ui  && npx vitest run --coverage --coverage.include='ui/src/**/*.ts'

Docker sets `HOSTNAME` in every container, and that keeps one branch of `Dockercompose.ts` from running under test.
The checkout path `/src` also matches the dashboard's `src/**/*.ts` coverage glob, so its test helpers get counted.

To drive the real server:

    cd /src/app
    DD_ANONYMOUS_AUTH_CONFIRM=true DD_STORE_PATH=/tmp/dd-store node dist/index.js

It listens on port 3000 and serves the API under `/api/v1` and the dashboard at `/`. Leave out
`DD_ANONYMOUS_AUTH_CONFIRM` to see the fail-closed state (`/health` returns 503, the API 401). For a login, set
`DD_AUTH_BASIC_<NAME>_USER` and `DD_AUTH_BASIC_<NAME>_HASH`; the docs page under
`content/docs/current/configuration/authentications/basic/` has a Node one-liner that makes the hash. Without a daemon
the watcher logs a connection warning and the server keeps running. To feed it containers, images or tags, serve a
stub Docker Engine API on a Unix socket and point `DD_WATCHER_LOCAL_SOCKET` at it, and a stub registry on loopback
through `DD_REGISTRY_CUSTOM_<NAME>_URL`. Agent mode is `node dist/index.js --agent` with `DD_AGENT_SECRET` and at
least one `DD_WATCHER_*`.

The server runs from `dist/`, so run `npm run build` in `app/` after changing backend source. `npm run build` in `ui/`
rewrites the tracked file `ui/src/boot/icon-bundle.json`; keep that file out of patches.

## How we rate severity

Name the attacker first. The same bug is rated by who can trigger it.

- Critical: remote code execution without credentials. An authentication bypass or session forgery that reaches the
  protected API, since that API controls containers. Unauthenticated access to an agent's API or to the edge agent
  endpoint.
- High: input controlled by an image publisher or a registry that reaches command execution (a hook provenance or
  grammar bypass, injection through hook or command environment values, argument injection into Trivy or cosign) or
  that changes what a recreated container runs. Disclosure of configured credentials: registry credentials sent to a
  host the operator didn't configure, secrets in responses, logs or debug dumps. An agent that gains code execution on
  the controller or control of another agent's host. Stored XSS from image, registry or container data that runs when
  a logged-in user opens the dashboard, and CSRF that triggers an update or other state change.
- Medium: anything that needs an authenticated session. Every authenticated user is already an administrator, so
  these never rate higher. Also: denial of service by an unauthenticated client or by a hostile registry or image
  (a crash, a hang, unbounded memory, a native-`RegExp` blowup), reflected XSS that needs a crafted link, and
  requests steered to internal addresses by a remote response when nothing sensitive comes back.
- Low: denial of service that needs an authenticated session. Hardening gaps with no demonstrated impact.

## Out of scope

- The operator attacking their own deployment, and anything that needs Docker socket access, the ability to set
  labels when creating a container, or the ability to change `DD_*` variables or mounted files.
- Documented opt-ins doing what they say: hooks and the command action running operator commands,
  `DD_HOOKS_ALLOW_IMAGE_LABELS=true`, anonymous access after `DD_ANONYMOUS_AUTH_CONFIRM=true`, root mode after
  `DD_RUN_AS_ROOT` and `DD_ALLOW_INSECURE_ROOT`.
- A request to a URL the operator configured is not SSRF. A remote response, redirect or image label that moves a
  request or a credential somewhere else is in scope.
- The gaps `SECURITY-ASSURANCE.md` already states (for example no response-size cap on some providers, redirects
  followed for icons and release notes), unless you can show impact beyond what it describes.
- The absence of roles.
- `e2e/`, `test/`, test files, fixtures and mocks. The marketing and docs site in `apps/web`, the demo in
  `apps/demo` and the docs in `content/`, unless the issue changes the shipped image or the release pipeline.
- Vulnerabilities in dev dependencies, and dependency CVEs with no reachable path from shipped code.

## Reports and patches

- One report per root cause. List variants of the same cause together.
- Say which boundary from this file is crossed and what the attacker ends up with.
- A reproducer against the running server is the most useful: the environment variables, the stub Docker or registry
  responses, the request, and what to look for. A failing Vitest test next to the affected module is the next best.
- Patch against `main` as scanned and fix the cause, not the one input. Add or update the neighboring `*.test.ts`
  (`*.spec.ts` under `ui/tests/`). `app/` and `ui/` both enforce 100% line, branch, function and statement coverage,
  so every new branch needs a test. Keep `npm run lint` (Biome) clean, and use the existing re2js helpers for any
  pattern that comes from a label.
- Commit subjects follow Conventional Commits, for example `fix(hooks): ...`.
