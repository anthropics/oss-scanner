# PegaProx threat model

PegaProx is a self-hosted web application for running several Proxmox VE clusters (plus
Proxmox Backup Server and XCP-ng) from one place: VM and container lifecycle, migration,
load balancing, HA, backups, consoles, node updates and user management. It is one Python
process (Flask on gevent) with a React frontend, deployed as a Docker image, a Debian
package, a VM appliance or from git.

To do its job it holds the keys to the infrastructure it manages: root@pam passwords, API
tokens and SSH private keys for every cluster, and it runs commands on the nodes as root
over SSH. A flaw in PegaProx is therefore usually a flaw in every hypervisor behind it.

## Where untrusted input enters

- **The network.** The web UI and REST API listen on one HTTPS port (5000 by default). The
  VNC and SSH console WebSockets listen on the next two ports. Reachable without a session:
  login, the first-run setup (only until an admin exists), OIDC authorize/callback, WebAuthn
  login, `/api/health`, and the Proxmox auto-install answer/progress endpoints (authenticated
  by a per-run token). Everything else needs a session cookie or an API token.
- **Authenticated users with limited rights.** Roles are admin, user and viewer, refined by
  per-cluster/per-VM permissions and pools, and by tenants (a tenant sees only its own
  clusters and guests). API tokens carry a role and can be scoped further. These users are
  untrusted: they must not reach admin, another tenant, command execution on a node, or any
  stored secret.
- **Data from the managed systems.** VM and container names, notes/descriptions, tags,
  task logs, guest agent output, storage content, PBS snapshots, node and network names.
  The person who owns a guest controls much of this, so it is untrusted: it must not run
  as script in a PegaProx user's browser and must not reach a shell command unescaped.
- **Outbound requests a user can steer.** Webhooks, SMTP, OIDC discovery, ACME, image
  catalogs, ESXi/XCP-ng import sources and similar. URL checks live in
  `pegaprox/utils/url_security.py`.
- **HA peers and the witness.** PegaProx instances in an HA pair and the witness talk to
  each other with a shared secret.

Global admins are trusted. Running commands on nodes, opening a node shell, installing
plugins and changing server settings are features for them, not vulnerabilities.

## Components that matter most

- `pegaprox/app.py`: the request gate in front of every route (CSRF Origin/Referer check,
  IP allowlist, security headers) and the server start.
- `pegaprox/utils/auth.py`, `pegaprox/utils/rbac.py`, `pegaprox/api/auth.py`,
  `pegaprox/api/users.py`, `pegaprox/utils/oidc.py`, `pegaprox/utils/ldap.py`,
  `pegaprox/api/webauthn.py`: sessions, 2FA, OIDC/LDAP, roles, permissions, tenants.
- `pegaprox/api/vms.py` (also the VNC/SSH console servers), `pegaprox/api/nodes.py`,
  `pegaprox/api/clusters.py`, `pegaprox/api/storage.py`, `pegaprox/api/pbs.py`,
  `pegaprox/api/settings.py`: the bulk of the REST API and its permission checks.
  `pegaprox/api/.ssh_ws_server.py` is generated from code in `vms.py`.
- `pegaprox/core/manager.py`, `pegaprox/core/pbs.py`, `pegaprox/utils/ssh.py`,
  `pegaprox/utils/ssh_security.py`: everything that talks to a node, including how shell
  commands for the nodes are built and how host keys are pinned.
- `pegaprox/core/db.py`: SQLite storage; secrets are encrypted with AES-GCM.

Less important: `plugins/` (optional, installed by an admin), `web/Dev/` (build tooling),
`packaging/`, `tests/`.

## How to exercise it

- The test suite is in `/src/tests` and runs offline: `python -m pytest -q tests/<file>.py`.
  The full suite has about 13,000 tests and takes close to an hour on one core.
- The `_integration_app` fixture in `tests/conftest.py` builds the real Flask app on a
  temporary database. Requests through its test client go through the same gate and routes
  as in production; `tests/test_csrf_origin.py` and `tests/test_authz_isolation.py` show the
  pattern. The `api` and `seed` fixtures give a client with seeded users, roles and tenants.
- No Proxmox cluster is reachable offline. `make_fake_manager` in `tests/conftest.py` stands
  in for a cluster.
- `python pegaprox_multi_cluster.py` starts the server on ports 5000-5002 with a config in
  `./config`; the first visit shows the setup wizard.

## How we rate severity

- **Critical:** code execution on the PegaProx host or on a managed node without a session;
  login or 2FA bypass; reading stored cluster credentials, sessions or the encryption key
  without a session; anything that turns network access into root on a node.
- **High:** a viewer, user, restricted API token or tenant member reaching admin rights,
  another tenant's clusters or guests, command execution on a node, or stored secrets;
  script injection that runs in another user's session (data from a guest counts as
  attacker-controlled); a CSRF check bypass; path traversal that reads or writes files on
  the PegaProx host; SSRF that sends PegaProx's credentials or returns the response.
- **Medium:** blind SSRF; one tenant seeing another tenant's non-secret data (names, counts);
  a request without a session that stalls the server for everyone (the gevent loop is
  shared, so CPU-bound work in a request blocks all users); open redirect.
- **Low:** denial of service that needs a session; missing hardening without a working
  attack; self-XSS.

Please state in each report which role or tenant the attacker needs.

## Anything to leave alone

- The VM appliance ships with a documented default root password. This is intended.
- TLS verification towards Proxmox is off by default because self-signed node certificates
  are the norm; it is a per-cluster setting.
- Features of the global admin role (node shell, commands on nodes, plugins, updates).
- Vulnerabilities in dependencies, unless PegaProx code makes them reachable.
