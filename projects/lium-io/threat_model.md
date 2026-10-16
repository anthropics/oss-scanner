# Threat model

## What this project does and where untrusted input enters

Lium is a GPU rental marketplace on Bittensor Subnet 51. Providers list GPU machines. Renters rent them as Docker pods. This repository has the code that runs on provider machines and the validator that checks and scores them.

Components (all Python, FastAPI):

- **Executor** (`neurons/executor`): the node agent on each GPU host. It runs in a container with the host Docker socket, so it is root on the host. It serves an HTTP API (default port 8001) and an sshd (default port 2200).
- **Miner** (`neurons/miners`): the provider's agent. It keeps the list of its executors and talks to validators. In `CENTRAL_MODE` one miner serves many provider hotkeys.
- **Validator** (`neurons/validators`): connects to every miner, logs in to every executor over SSH, runs check scripts there (`src/miner_jobs`), scores the results and sets weights on chain. It also takes pod requests from the Lium backend over a WebSocket and creates, edits, backs up and deletes renter containers on executors.
- **Watchtower** (`watchtower`): updates the executor container. It pulls only an image digest that a validator hotkey signed.
- **Libraries**: `datura` (miner/validator request models and the WebSocket consumer), `lium_protocol` (validator/backend message models), `packages/lium-core` (shared config).

Trust: providers do not trust renters. The validator does not trust providers. A provider has full control of its own host and can change the executor and miner code. Nobody trusts the open Internet.

Untrusted input enters here:

- **Executor HTTP API** (`neurons/executor/src/routes/apis.py`, `middlewares/miner.py`, `dependencies/auth.py`). Anyone on the Internet can reach it. Each route must check a miner or validator hotkey signature, a nonce or a time window. `/upload_ssh_key` adds a key to root's `authorized_keys`.
- **Miner endpoints** (`neurons/miners/src/routes/validator_interface.py`, `consumers/validator_consumer.py`, `dependencies/auth.py`). The `/websocket/{validator_key}` WebSocket and the REST routes that submit or remove SSH keys and read pod logs. Callers must prove a validator hotkey that the miner allows.
- **Data that the validator reads from providers.** Miner WebSocket and REST replies (executor addresses, ports), and all output of commands that it runs over SSH on an executor (hardware scrape JSON, `docker` output, GPU checks). A provider controls all of this.
- **Renter values that the validator passes to an executor shell.** `ContainerCreateRequest` and related messages come from the Lium backend, but many fields come from the renter: `docker_image`, `dockerfile_content`, environment, ports, `custom_options`, `user_public_keys`, volume names, registry login. The validator puts them into `docker` commands that run as root on the executor host (`neurons/validators/src/services/docker_service.py`).
- **The renter container.** A renter is root inside the pod. Pods use the `sysbox-runc` runtime when `is_sysbox` is set. The host must stay safe from the pod.
- **Watchtower update source.** The signed digest endpoint and the registry.

## Components that matter most / least

- Most: the executor API and its auth, the executor `authorized_keys` handling (`services/ssh_service.py`, `services/miner_service.py`), the validator `docker_service.py` (command building, mounts, runtime, custom image build), the miner auth dependencies, and watchtower signature checks.
- In scope: the rest of `neurons/validators/src` (scoring, attestation, port checks, backups in `miner_jobs`), `neurons/miners/src`, `neurons/executor/src`, `datura`, `lium_protocol`, `packages/lium-core`, and the shell scripts the executor runs (`neurons/executor/*.sh`).
- Out of scope: the closed binaries `libverifyx.so`, `libinspector.so`, `libdmcompverify.so`, and the vendored `sysbox-ce_*.deb`. Also `e2e/`, `tests/`, `docs/`, `contrib/`, and the installer scripts in `scripts/`.
- Out of scope (not in this repo): the Lium backend and web app, the `lium` CLI and SDK (`Datura-ai/lium`), the Bittensor chain and SDK.

## How to exercise it

Each package has its own pdm venv. Run tests with `pdm run pytest tests/` in `neurons/executor` (after `mkdir -p tmp`), `neurons/miners` and `watchtower`. The validator tests need these variables:

```
cd /src/neurons/validators && BITTENSOR_WALLET_NAME=test_wallet BITTENSOR_WALLET_HOTKEY_NAME=test_hotkey \
  SQLALCHEMY_DATABASE_URI=sqlite:///test.db ASYNC_SQLALCHEMY_DATABASE_URI=sqlite+aiosqlite:///test.db \
  ENABLE_TDX_ATTESTATION=True TDX_VERIFIER_URL=http://localhost:8000/verify pdm run pytest tests/
```

`lium_protocol` and `packages/lium-core` tests run with `/opt/lium-libs/bin/python -m pytest tests`. The executor and miner apps are FastAPI apps; tests build them with `TestClient` and fake hotkeys. There is no GPU, chain or Docker daemon in the image, so tests that need one fail or skip. `test_scrape_infiniband.py::test_an_unreadable_sysfs_tree_is_not_reported_as_no_devices` fails as root, because root can read the "unreadable" tree.

## How you rate severity

- **Critical:** code execution as root on an executor host without a valid validator or miner signature. A renter pod that escapes to the host. Code execution on the validator from data a miner or executor sends. A watchtower update that runs an image no validator signed. Theft of a validator or miner hotkey.
- **High:** auth bypass on executor or miner routes (for example, adding an SSH key, or reading another pod's logs, without the right signature). Shell or argument injection from a renter field into a command on the executor host. One renter reaching another renter's pod, volume or backup. A provider passing the validator's GPU or hardware checks with fake data, so it earns emission or rent for hardware it does not have.
- **Medium:** replay of a signed request inside its time window. One miner or executor stalling or crashing the validator's cycle for other miners. Leaks of internal data that are not secrets.
- **Low:** crashes or hangs of one executor or miner from bad input, log injection, missing hardening without an attack path.

## Anything to leave alone

- A provider who has root on its own host and reads or changes pods on that host. This is the known trust limit of the network.
- Validator checks that a provider defeats only by patching the closed `.so` verifiers. Report it only if the Python side accepts a result it should reject.
- Commands that a validator or the backend sends on purpose with a valid signature. These are trusted parties.
- Outdated dependencies with no path from Lium code.
- Default or example values in `docker-compose*.yml`, `.env` examples and `config.toml`.

## How reports should look

Name the actor (Internet, renter, provider, miner, validator), the input it controls, the file and function that uses it, and the impact. Add a test or `curl` reproducer and a short patch if you can.
