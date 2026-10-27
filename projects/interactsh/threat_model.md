# Threat model

## What this project does and where untrusted input enters
Interactsh detects out-of-band interactions. `interactsh-server` is an internet-facing, multi-tenant service: DNS, HTTP/HTTPS, SMTP/SMTPS, and optionally LDAP, FTP/FTPS, SMB and an NTLM responder. It records every interaction against a correlation ID. Clients register with an RSA public key and a secret key, then poll for their interactions, which come back AES-encrypted. Clients can also upload files that the server hosts for targets to fetch. Public servers run this code, so the server is the primary target.

Untrusted:
- Every packet, connection and request from the internet, on every protocol.
- The client API: `/register`, `/poll`, `/deregister`, `/upload`, `/f/` hosted files, `/s/` static files, `/metrics`. Clients are untrusted to each other, and anyone can call these without a token unless `-auth` is set.
- Query parameters and `/b64_body:` paths that shape responses under `-dynamic-resp`.
- The `-origin-ip-header` value, which a client can spoof unless a trusted proxy sets it.
- Responses to `interactsh-client` and `pkg/client` from the server they poll or upload to.

Trusted: the operator's server flags and config, `-custom-records`, `-http-index`, `-http-directory` and `-ftp-dir` contents, TLS certificates and keys, the Redis instance, and the ACME CA.

## Components that matter most / least
- Tenant isolation is the main guarantee: one client must not read, delete, poison or overwrite another client's interactions or uploads, or learn its secret key.
- Correlation-ID and secret-key checks, `-auth`/`-token`, and the AES/RSA encryption of polled data (`pkg/server`, `pkg/storage`).
- Protocol parsers: DNS (`dns_server.go`), HTTP (`http_server.go`), SMTP, LDAP, FTP (including uploads), SMB and the NTLM responder (`smb_server.go`, `responder_server.go`, `ntlm_capture.go`).
- Uploads (`upload.go`, `upload_handler.go`): size and count limits, TTL cleanup, path handling inside the upload directory and `-ftp-dir`, and how hosted files are served (they must not become stored XSS on the server's origin).
- Static file serving (`/s/`, `-http-directory`): no path traversal outside the directory.
- `-dynamic-resp`: attacker-chosen headers, body and status must not enable response splitting or script execution on the server's origin in a way that harms other users.
- Storage (`pkg/storage`): the disk store and the Redis store with its Lua scripts, eviction, and memory and disk limits.
- ACME and certificate reload (`pkg/server/acme`), including the DNS TXT records served for challenges.
- CORS (`-acao-url`) on the API.
- The client (`pkg/client`): decryption and parsing of polled data, upload requests, and the `-hc` health check.
- Out of scope: `cmd/benchmark-server`, `deploy`, `examples`, and test fixtures.

## How to exercise it
- `interactsh-server` and `interactsh-client` are in `/usr/local/bin`. Run the server locally with `-skip-acme -d test.local` (add `-upload`, `-dynamic-resp`, `-ldap`, `-smb`, `-ftp`, `-responder` and `-auth` as needed), then talk to it with the client, `dig`, `curl` or raw sockets.

## How you rate severity
- Critical: unauthenticated remote code execution on the server; arbitrary file write on the server.
- High: reading, deleting or tampering with another client's interactions or uploads; recovering another client's secret key or plaintext interactions; bypassing token auth; arbitrary file read (including path traversal through `/s/`, `/f/` or FTP); a single request or packet that crashes the whole server; memory corruption.
- Medium: resource exhaustion (memory, disk, goroutines, Redis) with modest traffic, including bypassing upload limits; stored or reflected XSS on the server's origin; DNS behaviour that enables amplification; spoofing the recorded source of an interaction when no trusted proxy is configured.
- Low: client crash on a malformed server response; information leaks with no cross-client impact.

## Anything to leave alone
- The server recording any interaction sent to its domains, and capturing NTLM hashes on its SMB and responder services: that is its purpose.
- Content chosen by the client that registered a correlation ID, served back under that ID, such as its own uploads or `-dynamic-resp` output for its own requests, as long as it cannot reach other clients.
- Volumetric DoS that needs large bandwidth.
- Behaviour driven by the operator's own config, files and certificates.
