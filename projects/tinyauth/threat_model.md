# Threat model

## What this project does and where untrusted input enters

Tinyauth is a lightweight authentication and authorization server for self-hosted applications. It can act as authentication middleware or as a standalone authentication server, with support for OAuth, LDAP, and access controls. It integrates with reverse proxies such as Traefik, Nginx, and Caddy.

Tinyauth has two core components: an OpenID Connect server and a set of forward-auth handlers.

The OpenID Connect server operates according to a standardized protocol, but incoming requests must never be assumed to be valid or specification-compliant. All input is untrusted and must be validated before use.

The forward-auth handlers receive requests from different proxies using different headers and conventions, without a single standardized interface. All incoming data must be treated as untrusted and validated before making security decisions, such as allowing or denying access.

## Security-critical components

### OpenID Connect server

The OpenID Connect server must follow the specification as closely as possible and fail closed when required validation fails. Although the protocol is standardized, its inputs remain untrusted, and implementation errors can compromise authentication or authorization.

### Forward-auth handlers

The forward-auth handlers require particular attention. Each proxy integration relies on different headers and request conventions. Attacker-controlled headers or other request data must not be mistaken for trusted proxy context or authentication information.

When reviewing these handlers, consider how the proxy constructs the request, which values an attacker can influence, and how Tinyauth validates those values before using them.

### Access-control service

The access-control service is closely tied to forward-auth. Its decisions depend on the request context supplied by the proxy. Injected or malformed values can cause access controls to incorrectly allow or deny a request.

Reviewing this service also requires considering the Docker and Kubernetes services, which provide access-control configuration.

### Session management and account handling

Session management and account handling are also security-critical. This includes the creation, validation, and expiration of sessions, along with authentication and identity handling for local bcrypt users, OAuth users, LDAP users, and Tailscale users.

## How to exercise it

See the `AGENTS.md` file for the available make commands. You can build the Tinyauth binary with the provided make commands and run it with a `.env` derived from the `.env.example`. You cannot however spin up a Docker stack so you will have to work with CLI commands (you have `curl` available) or Go test files.

To test the code directly, including against mock providers, refer to the existing `*_test.go` files for examples of the testing approach used in Tinyauth.

## How to assess severity

Assess severity based on demonstrated impact and exploitability. The following categories serve as guidelines.

### Critical

- Injection of attacker-controlled values into the trusted proxy context.
- Flaws in access-control evaluation that can bypass access restrictions.
- Bypasses of the OpenID Connect authorization flow.
- Bypasses of local, OAuth, LDAP, or Tailscale authentication.

### High

- Incorrect escaping or unescaping of security-sensitive values.
- Incorrect validation of URLs, paths, or other security-sensitive inputs.
- Incorrect generation of security-sensitive values, such as session cookies or OpenID Connect tokens and identifiers.

### Medium

- Cross-site request forgery (CSRF).
- Check-then-act race conditions.
- User enumeration.
- Denial of service (DoS).

## Intentional deviations

Do not report an intentional, clearly documented deviation from a specification solely because it is noncompliant.

A documented deviation remains in scope if it introduces a security vulnerability.
