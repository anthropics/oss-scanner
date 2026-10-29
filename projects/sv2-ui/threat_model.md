# Threat model: sv2-ui

## What this project does and where untrusted input enters

sv2-ui is the setup wizard and monitoring dashboard of the Stratum V2 Reference Implementation (SRI) mining stack. A miner runs it as a Docker container (also packaged as an Umbrel app) on a machine on their own network, in the JD modes alongside a Bitcoin Core node, and opens it in a browser. From there they create an admin password, enter a payout address and pool credentials, and sv2-ui generates the TOML configuration for, starts, stops and monitors two applications from https://github.com/stratum-mining/sv2-apps: the Job Declarator Client (JDC) and the Translator Proxy (tProxy), which it runs as Docker containers through the Docker socket mounted into its own container.

A root package with two npm workspaces, one TypeScript codebase:

- `server/`: the backend, an Express app (`server/src/index.ts`). It serves the built frontend, a JSON API for the wizard and dashboard, the admin password and recovery-key flow (`auth-store.ts`, `sessions.ts`), the Docker orchestration (`docker.ts`, via dockerode), config generation (`config-generator.ts`), format validation of the pool fields (`pool-validation.ts`), the Bitcoin Core checks and the LAN address probe (`bitcoin-rpc-validator.ts`, `bitcoin-socket-validator.ts`, `bitcoin-socket-exists.ts` and `host-network-probe.ts` export scripts that `docker.ts` runs in short-lived helper containers), persistent state under `CONFIG_DIR` (`state.ts`, `atomic-write.ts`), the container log routes under `/api/logs/*` (parsed in `server/src/logs/` and `active-pool.ts`), and the `/translator-api` and `/jdc-api` routes that relay the JDC and tProxy monitoring APIs to the dashboard.
- `src/`: the React frontend (Vite), served by the backend.
- `shared/`: code and the OpenAPI schema (`shared/openapi.json`, copied from sv2-apps) shared by both, including the sv2-apps image selection (`shared/src/images.ts`).

Where untrusted input enters:

1. **HTTP requests to the backend** from anything that can reach the device's web interface: the browser of the operator, but also any other host on the same LAN, and any web page the operator's browser visits (cross-site requests; see `request-origin.ts`). Before login, the only legitimate actions are creating the first password, logging in, and recovering with the recovery key, plus two reads: `/api/health` (which pings the Docker daemon to report whether it is reachable) and `/api/auth/state`. After login the API controls the Docker daemon.
2. **The sv2-apps containers' monitoring APIs and logs**, which the backend relays (`/translator-api`, `/jdc-api`) or reads, parses and serves (`/api/logs/*`, `server/src/logs/`, `active-pool.ts`) to the dashboard. They run on the operator's machine, but their content reflects what remote pools and miners sent, so treat it as untrusted data when it is parsed or rendered.
3. **The helper containers.** The backend never connects to a pool itself (pool fields are format-checked only; JDC and tProxy are what connect to pools). Two kinds of checks run as throwaway containers created through the Docker daemon (`docker.ts`). The Bitcoin Core checks, behind `/api/validate/*` and, with the saved `socket_path`, before every start (`/api/setup`, `/api/config`, `/api/restart` and the auto-start reconciler in `auto-start.ts`): `probeBitcoinSocketWithDocker` mounts the parent directory of the `socket_path` the operator sends to `POST /api/validate/bitcoin-socket` (expanded under `HOST_HOME`; read-write, for the existence check) and then the socket itself (read-only); `autoDiscoverBitcoinRpc` mounts the default Bitcoin Core data directories read-only, on the host or bridge network. The LAN address probe, behind `GET /api/miner-telemetry/suggestion`: `detectHostLanAddress` runs `host-network-probe.ts` on the host network.
4. **Persistent state and config files** under `CONFIG_DIR`, written by the backend itself; treat them as trusted, except that the generated TOML is consumed by JDC and tProxy, so operator input must not be able to inject configuration it did not intend.

The Docker socket is the crown jewel: whoever can issue arbitrary requests to it owns the host. The backend must only ever perform the specific container operations the product needs, on the images it selects.

## Components that matter most / least

Most important, in this order:

1. Authentication and sessions: password and recovery-key creation, verification and storage, session issuance and expiry, and the origin checks that keep a cross-site page from using an operator's session.
2. Every API route that reaches the Docker daemon or the filesystem under `CONFIG_DIR`: which routes require a session, and whether any request parameter can change which image is run, which volumes or sockets are mounted, which command is executed, or which file is written.
3. Config generation: whether operator input (payout address, pool URL, credentials, worker names) can break out of the TOML value it is written into, or make JDC or tProxy mine for a payout the operator did not choose.
4. The Bitcoin Core checks: which host path a request can get bind-mounted into a helper container (and whether read-write), what the helper script reads and returns to the caller, and hangs on a socket or node that never answers.
5. The frontend's rendering of data that came from the monitoring APIs or from the operator (cross-site scripting), and anything it stores in the browser.
6. The dashboard arithmetic (hashrate, share and payout numbers), which is accuracy rather than security.

Out of scope: the JDC and tProxy applications themselves (their own project, https://github.com/stratum-mining/sv2-apps), Bitcoin Core, Docker, the Umbrel packaging, `docs/`, CI configuration and the test fixtures. `src/types/api-generated.ts` and `shared/openapi.json` are generated and copied from sv2-apps; a finding about the schema belongs there.

## How to exercise it

The image is offline. All npm packages are installed, and the frontend (`dist/`) and the backend (`server/dist/`) are built in `/src`.

- **Tests**: `npm run test` (frontend), `npm run test:server` (backend) or `npm run test:all`. They run on `node:test` and sit next to the code they cover as `*.test.ts(x)`; `server/src/docker.test.ts` shows how the Docker calls are mocked with `node:test`'s mocks.
- **Type check and lint**: `npm run typecheck`, `npm run lint`.
- **The backend**: `node --import tsx server/dist/index.js` starts it on `PORT` (8080) with its state under `CONFIG_DIR`, serving the frontend from `/src/dist` (leave `NODE_ENV` unset for that). There is no Docker daemon in the image, so the routes that manage containers, read logs, run the Bitcoin Core checks (`/api/validate/*`) or the LAN probe (`/api/miner-telemetry/suggestion`) fail at the Docker call; authentication, sessions, state, format validation and TOML generation run before that point and can be driven with `curl` against `127.0.0.1:8080`. `server/src/index.ts` lists the routes, with `PUBLIC_API_PATHS` naming the ones that need no session, and `/translator-api` and `/jdc-api` proxying to the two containers' monitoring APIs.
- **The frontend**: served by the backend from `dist/` once built; `npm run preview` serves it on its own.
- **Config generation** can be exercised without Docker through `server/src/config-generator.ts` and its tests; `npm run check:sv2-app-config` feeds the output to the real images but needs the network and a Docker daemon, so it does not run here.

## How you rate severity

A finding counts when someone who is not the logged-in operator can affect the host, the mining configuration or the operator's session, or when the operator's own input ends up somewhere it should not. Say whether the attacker is unauthenticated, a LAN host, a cross-site page, or a hostile pool or monitoring peer, and which configuration the reproducer needs.

- **Critical**: an unauthenticated request, or a cross-site request made by a logged-in operator's browser, that performs a container, image, network or volume operation through the Docker daemon, writes under `CONFIG_DIR` (other than the credential file the first-password and recovery routes write by design), or starts, stops or reconfigures JDC or tProxy (a changed payout address or pool credentials included). Any way for a request to run an image, command, mount or socket other than the ones the product selects. Authentication bypass, password or recovery-key recovery from stored data without the secret, or a session usable without having logged in.
- **High**: a change of payout address or pool credentials that the operator did not make, by a path the Critical bullet does not cover (a logged-in request to one route that changes a field another route owns, a monitoring response or log line that is acted on). A value the UI accepts that changes the generated TOML beyond the field it was typed into: that is injection, not the operator acting against their own interest. A host path the logged-in operator did not type mounted into a helper container (mounting the parent of the typed `socket_path` read-write is the product's existence check), or a helper that does more than its fixed script and returns file contents to the caller. Stored cross-site scripting through data a hostile pool or miner controls, through the monitoring relay or the log routes.
- **Medium**: an unauthenticated request that crashes or hangs the backend, or exhausts its memory. Disclosure of pool credentials, the payout address or the host's configuration to an unauthenticated client. Reflected cross-site scripting. Missing or wrong session expiry.
- **Low**: a defect that needs the operator to be logged in and to act against their own interest, a non-default setting, or a race with no demonstrated effect. Information in log output.

Hashrate or payout numbers that are wrong on the dashboard are bugs, not vulnerabilities; report them only when a peer can make them wrong on purpose and that has a security consequence.

## How to report

- Give a reproducer that runs in this image: a `node:test` next to the code, or a `curl` sequence against the backend, with the exact requests sent and what was observed.
- Name the route or module, and whether the attacker needs a session, a LAN position, a cross-site page, or control of a pool or monitoring peer.
- Propose a minimal patch against `main` with a regression test, following the test patterns already in the repository, and keep unrelated refactoring out of it.
- Report one root cause once.

## Anything to leave alone

- Sessions live in memory and end on restart (see `README.md`); logging the operator out on a restart or update is the documented behaviour.
- The backend mounts the Docker socket by design: that it can manage containers is the product, and `/api/health` answering without a session with the result of a Docker ping is part of it. The finding is any way to make it do more than the operations the product needs, not the capability itself.
- Deleting `credential.json` from the config directory resets the password while keeping the mining configuration, on purpose, for an operator with shell access to the host; shell access on the host is outside the model.
- The product serves plain HTTP on the LAN and relies on the operator's network boundary; the absence of TLS is known. Report what an attacker on that LAN can do beyond observing traffic.
