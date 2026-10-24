# Threat model

## What this project does and where untrusted input enters
Lium is a Python SDK and CLI (`lium`, package `lium.io`) to rent GPU pods on lium.io. The user runs it on their own
machine. It calls the Lium REST API, then connects to the pods over SSH (paramiko, the `ssh` binary, scp, rsync).
A pod runs on hardware that a third-party provider (a Bittensor miner) controls. Treat these inputs as untrusted:

- **The pod and the provider host.** SSH host keys, command output, files that `lium scp`/`rsync`/`cp`/download
  copy back, and the result file of a `@lium.machine` call (`lium/sdk/decorators.py`, `lium/sdk/result_codec.py`).
  A malicious provider must not get code execution, file writes outside the target path, or credentials on the
  user's machine.
- **API responses.** Pod names, hosts, ports, SSH users, template and image names, error text. The CLI puts some
  of these into shell commands (`ssh`, `rsync -e`, remote `bash -lc`) and into terminal output (rich markup,
  ANSI escapes).
- **User arguments that become shell text.** `lium exec`, `lium rm --in/--at`, remote paths, env values. They
  are quoted with `shlex` in `lium/sdk/client.py`, `lium/sdk/detach.py`, `lium/cli/commands/exec.py`.
- **Release downloads.** `lium update` fetches a binary and `checksums.txt` from GitHub (`lium/cli/self_update.py`).

Secrets on disk: the API key in `~/.lium/config.ini` (or `LIUM_API_KEY`), SSH private keys, pinned pod host keys,
and the provider portal JWT (`lium/provider/token_store.py`, written with mode 0600).

## Components that matter most / least
- Most: `lium/sdk/client.py` (SSH, exec, scp, rsync, pod-to-pod transfer, host-key pinning), `lium/sdk/_hostkeys.py`,
  `lium/sdk/decorators.py` + `result_codec.py`, `lium/sdk/config.py`, `lium/cli/self_update.py`,
  `lium/provider/` (wallet and portal auth).
- Less: `lium/cli/commands/mine.py` and `lium/cli/mine/` run on the provider's own node as root with the
  provider's own input. Shell injection there is in scope only if a remote party (API, pod) controls the input.
- Out of scope: `docs/`, `examples/`, `e2e/` (live tests), `scripts/`, packaging (`lium.spec`, `Dockerfile.build`).
  The Lium server and the pod images are separate projects.

## How to exercise it
- `cd /src && pytest test/ -q` runs the unit tests offline. The venv is on PATH; `lium --help` works.
- There is no network. Mock the API with `responses` and the SSH side with `pytest-mock`, as the tests do.

## How you rate severity
- Critical: a pod, provider, or API response gets code execution on the user's machine, or steals the API key,
  SSH private key, or wallet keys.
- High: a pod writes files outside the chosen local path; shell injection into a remote command from an API field;
  host-key pinning bypass (silent MITM without `LIUM_SSH_INSECURE=1`); update installs a binary that fails the
  checksum.
- Medium: secrets written with loose file modes or printed to logs/telemetry; terminal escape injection that
  hides or fakes output.
- Low: DoS or crash of the local CLI from a bad API response.

## Anything to leave alone
- `@lium.machine` sends the caller's own arguments to the pod as a pickle. The caller owns that pod, so this is
  by design. Unpickling anything that comes back from the pod is a real bug.
- Trust on first use for pod host keys is by design. `LIUM_SSH_INSECURE=1` turns off checks on purpose.
- The user's own config file, env vars, `$EDITOR`, and installed `lium.plugins` entry points are trusted.
