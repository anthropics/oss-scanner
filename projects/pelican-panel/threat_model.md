# Pelican Panel threat model

Pelican Panel is a self-hosted web application for managing game servers. An operator (often a small
hosting company or a community) installs it, attaches one or more nodes running Wings (the daemon), and
gives accounts to users who each control their own servers.

## Actors and trust levels

- **Root admin:** fully trusted; can do anything in the panel.
- **Admin roles:** trusted only for the permissions their role grants.
- **Server owner:** an ordinary user; controls only servers they own.
- **Subuser:** a user given a subset of permissions on someone else's server.
- **API clients:** application keys (admin) and client keys (user), scoped like their owner.
- **Wings nodes:** authenticate to the panel with a per-node token; trusted for their own servers only.
- **Unauthenticated visitors:** can reach login, password reset, 2FA and OAuth flows.

## What matters most

1. **Cross-tenant access:** one user reading or changing another user's server, files, databases,
   backups, schedules, allocations or subusers through the web UI, the client API or Livewire/Filament
   actions. This is the most important class of bug.
2. **Privilege escalation:** a subuser exceeding their permissions; a user or limited admin reaching
   admin functions; a client API key reaching application API routes.
3. **Authentication:** login, 2FA, password reset, OAuth, session and API key handling.
4. **Node trust:** a compromised or malicious Wings node acting on servers that belong to other nodes,
   or the panel sending node secrets to the wrong node.
5. **Egg and plugin input:** eggs (server templates) contain startup commands, install scripts and
   variables that end up executed on nodes. Admin-supplied eggs are trusted; user-editable variables
   are not and must be validated against the egg's rules.
6. **Injection:** SQL injection, stored XSS in names and descriptions, SSRF from URL fields
   (e.g. remote file downloads, webhooks), and file path handling.

## Out of scope

- Actions a root admin can already take.
- Denial of service that needs an authenticated admin.
- Vulnerabilities in third-party plugins that are not in this repository.
