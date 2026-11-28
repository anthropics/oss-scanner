# Threat model

The authoritative description of the deployment model is `docs/concepts/security.rst`. This file
summarises it and adds how we rate findings.

## What this project does and where untrusted input enters

Backend.AI is a multi-tenant platform that runs users' workloads (notebooks, training jobs, model
serving) in containers on shared GPU clusters. Tenancy is domain → project → user, and the roles are
superadmin, domain admin and user.

Main components (under `src/ai/backend/`): the webserver (`web/`, the user-facing gateway), the manager
(`manager/`, REST and GraphQL APIs), the app-proxy (`appproxy/`, access to apps inside sessions), the
storage-proxy (`storage/`, virtual folder file access), the agent (`agent/`, runs containers on compute
nodes), and the code placed inside user containers (`kernel/`, `runner/`).

Untrusted input comes from:

1. authenticated users, through the public APIs;
2. unauthenticated clients of the public endpoints;
3. code running inside a user's own container, which users control by design;
4. content users create that others later use (images, folder contents, names, model definitions).

Trusted: operators and their configuration, superadmins, the internal network between management
components, and container images an admin registered. As `docs/concepts/security.rst` describes, compute
nodes must not be reachable from untrusted networks.

## Components that matter most / least

What we most want found: users acting as other users or crossing a domain/project boundary, gaining a
higher role, bypassing authentication, escaping their container or their storage area, reaching another
user's session, injection, server-side request forgery into the management zone, and secrets disclosed to
users.

Lower priority: the client SDK and CLI, the installer, developer tooling, tests and docs.

## How to exercise it

- The development environment is in `/src/.venv`. Run tests with `python -m pytest <path>` from `/src`.
- Tests that need no external services include `tests/unit/common`, `tests/unit/kernel`,
  `tests/unit/webserver`, `tests/unit/storage_proxy` and `tests/unit/client`. Many manager and agent
  tests need PostgreSQL, Redis/Valkey and etcd and cannot run here; use them as references.
- Handlers can be exercised in-process with aiohttp's test client, as the unit tests do.

## How you rate severity

- Critical: unauthenticated remote code execution on a management component; container escape to the
  host from a normal user session; authentication bypass that lets anyone act as any user.
- High: an authenticated user acting as another user, crossing a domain/project boundary, reading or
  writing another user's data, or gaining admin rights; SSRF into the management zone with a readable
  response; disclosure of other users' or services' secrets.
- Medium: problems limited to the attacker's own project; cluster-wide denial of service by a normal user;
  SSRF without a readable response; disclosure of non-secret metadata across tenants.
- Low: issues that need a domain admin acting within their own domain, self-DoS, and missing hardening
  without a demonstrated exploit.

A superadmin or operator using powers they are meant to have is not a vulnerability.

## Anything to leave alone

- Users running arbitrary code or using their allotted resources inside their own container.
- Findings that need direct network access to compute nodes from outside the cluster.
- Default values in sample configs and development setups.
- Dependency advisories without a reachable path in this code.

## How to report

Please include reproduction steps, the lowest privileges needed, the relevant configuration, and a
proposed patch where possible.
