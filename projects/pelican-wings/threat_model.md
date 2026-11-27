# Wings threat model

Wings is the node daemon for Pelican Panel. It runs as root (or with Docker access) on each host and
runs every game server in its own Docker container. Users never log in to Wings directly: the panel
issues short-lived signed JWTs that Wings verifies, and the panel authenticates to Wings with the
node's token.

## Actors and trust levels

- **The panel:** trusted (holds the node token).
- **Users:** reach Wings through panel-issued JWTs for websockets, file uploads and downloads, and
  backups, and through SFTP with panel-checked credentials. Each user is limited to their own servers
  and to the permissions in their token.
- **Game server processes:** fully untrusted code running inside containers; they control every file
  in their server's data directory.

## What matters most

1. **Escaping the server directory:** path traversal, symlink and hardlink tricks, archive extraction
   (zip, tar, rar, 7z) or file operations that read or write outside a server's data directory. The
   server itself can plant symlinks at any time, so time-of-check/time-of-use races count.
2. **Container isolation:** server settings, egg variables, mounts, or Docker options that give a
   container host access, privileges or other containers' data.
3. **Cross-server access:** a JWT, SFTP login, websocket or backup request for one server touching
   another.
4. **Authentication:** JWT verification (algorithm, expiry, audience, permissions), SFTP auth through
   the panel, and the node token.
5. **Remote downloads and backups:** SSRF from "pull file from URL", and backup restore paths.
6. **Resource limits:** disk, memory and process limits that a server can bypass to harm the host.

## Out of scope

- Actions the panel (node token holder) can already take.
- Host misconfiguration by the operator.
