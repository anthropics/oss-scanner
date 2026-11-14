# Threat model

## What this project does and where untrusted input enters
Wings is the Go daemon that runs on each Pterodactyl node. It launches game servers in Docker containers and serves their files, console and backups. The Panel is its control plane. Untrusted input enters through:
- The HTTP API and websocket (`router/`), reached by users with short-lived JWTs that the Panel signs (`router/tokens`). The JWT names one server and a set of permissions; it must not reach any other server or permission.
- The SFTP server (`sftp/`), where users log in with credentials the Panel validates.
- Server files. Everything inside a server's data directory is controlled by the server's user, including symlinks, archive contents and file names. The filesystem layer (`server/filesystem`, `internal/ufs`) must keep every operation inside that directory.
- Archive extraction, remote file downloads (`server/filesystem`, `router/downloader`), backup restore, and config file parsing for eggs (`parser/`), all on user-controlled content.
- Console output and commands sent through the websocket.
- The Panel's own responses are trusted for server configuration, except that a compromised Panel should not be able to change host paths such as `allowed_mounts` or the data directory through a remote update.

## Components that matter most / least
- Most: escaping a server's data directory (path traversal, symlink and TOCTOU races, archive slips), container escape or host access through mounts and Docker options, one server's user reaching another server, JWT validation and scope checks, SFTP authentication and permission checks, SSRF from the downloader to internal hosts.
- Less: diagnostics and CLI commands an operator runs by hand on the host (`cmd/`).
- Out of scope: vulnerabilities in Docker itself or the kernel, and anything that needs root on the node already.

## How to exercise it
- `go test ./...` runs the unit tests. Most filesystem tests use a temporary directory and need no Docker.
- `/usr/local/bin/wings` is the built daemon; it needs a `config.yml` and a Docker socket to run fully, so prefer tests in `server/filesystem`, `internal/ufs`, `router` and `parser` to reproduce findings.

## How you rate severity
- Critical: code execution on the host or container escape; reading or writing files outside the server's data directory as an ordinary server user; access to another server's files or console.
- High: a JWT or SFTP user exceeding its granted permissions on its own server in a way that reaches files or credentials; SSRF from the downloader to internal or metadata addresses; disk quota bypass that can fill the host.
- Medium: denial of service that takes down the whole daemon from a single server's user; information disclosure about other servers.
- Low: denial of service limited to the attacker's own server, missing hardening.

## Anything to leave alone
- Do not report that a server's user can run arbitrary code inside their own container. That is the product.
- Do not report findings that need the operator to change `config.yml` to an insecure value.
