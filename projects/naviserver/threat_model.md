# NaviServer threat model

## Purpose and scope

NaviServer is a multithreaded server written in C and Tcl.
This scan covers the NaviServer repository, including its bundled
modules and Tcl libraries.

Prioritize remotely reachable server code, while also examining
security-sensitive APIs exposed to applications.

External modules and applications maintained in other repositories
are outside this enrollment's scope. Problems in NaviServer's
integration with dependencies remain in scope.

## Trust boundaries

Treat remote clients as untrusted. This includes request methods,
targets, headers, bodies, uploaded files, connection timing, and
protocol state transitions.

Treat upstream HTTP responses as untrusted when NaviServer acts as
an HTTP client or reverse proxy.

Configuration files, installed Tcl application code, and loaded
native modules are trusted administrator-controlled code. Executing
this code is an intended capability.

However, untrusted request data must not become executable Tcl,
shell commands, or filesystem paths through unintended interpretation.

Virtual servers and concurrent requests may share a process.
Do not assume that virtual servers isolate mutually hostile Tcl
applications. Nevertheless, request data and credentials must not
leak between unrelated requests or virtual servers through core bugs.

## Security properties and review priorities

- Memory safety when parsing or processing untrusted data.
- Consistent HTTP message framing, including Content-Length,
  Transfer-Encoding, connection reuse, and proxy interactions.
- Correct URL decoding, normalization, routing, and filesystem access.
- Prevention of unintended access outside configured document roots.
- Correct handling of authentication and authorization where enforced
  by bundled components.
- Isolation of request state across threads, reused connections,
  and Tcl interpreters.
- Safe handling of uploads, temporary files, and CGI execution.
- Correct TLS certificate and hostname verification where required
  by the configured API behavior.
- Enforcement of configured resource limits, timeouts, and cleanup.
- Prevention of unintended disclosure through responses or logs.

For proxy-related findings, describe both ends of the interaction
and the relevant configuration.

For SSRF findings, show how an attacker controls the destination
despite an intended restriction. An HTTP client API accepting a URL
from trusted application code is not sufficient by itself.

## How to exercise findings

Use the tests/ suite and small, focused reproductions.

Provide the build options, Tcl version, enabled modules, configuration,
and exact request or API call needed to reproduce a finding.

Prefer local reproductions with loopback clients and upstream servers.
Reproductions must work without external network access.

For memory safety findings, include sanitizer output where practical.
For concurrency findings, explain the interleaving and demonstrate
the failure repeatedly where possible.

## Severity guidance

Assess severity using attacker access, required configuration,
exploit reliability, and demonstrated impact.

- Remote code execution or arbitrary memory writes reachable by an
  unauthenticated client are high or critical, depending on evidence.
- Memory corruption should be reported even when code execution
  has not been demonstrated; distinguish proven impact from inference.
- Unauthorized file access, credential disclosure, authorization
  bypass, and request smuggling depend on the actual deployment
  requirements and resulting access.
- Remote process termination, persistent resource exhaustion, or
  disproportionate CPU consumption generally warrants medium or high
  severity, depending on effort and service impact.

Do not assign severity solely from a weakness category.

## Reporting expectations and exclusions

Include the source location, attacker-controlled input, reachable
call path, violated security property, reproduction, and impact.

Distinguish default behavior from behavior requiring optional modules
or non-default configuration. Optional features remain in scope.

Do not report trusted administrators' ability to execute Tcl or load
native code as a vulnerability.

Application-specific injection or authorization mistakes require
evidence of a defect in NaviServer or its bundled code.

A dependency advisory alone is insufficient: establish relevance
to NaviServer's actual use of the dependency.

Prefer fixes with focused regression tests that preserve documented
API behavior.

## Dependencies: Tcl

Tcl is a third-party dependency. Its source is included in the image
to build and test NaviServer.

Standalone vulnerabilities in Tcl internals are outside this scan's
scope. Do not report Tcl findings solely because its source is present
or because the installed version matches an advisory.

NaviServer's use of Tcl remains in scope, including incorrect C API
use, reference counting, object lifetimes, interpreter reuse,
thread handling, and unintended evaluation of untrusted input.

Executing trusted application Tcl code is an intended capability.

For any Tcl-related finding, identify the defect in NaviServer and
demonstrate how it is reachable through NaviServer.

## Dependencies: OpenSSL

OpenSSL is a third-party dependency. Its source is included in the
image to build and test NaviServer.

Standalone vulnerabilities in OpenSSL internals are outside this
scan's scope. Do not report OpenSSL findings solely because its source
is present or because the installed version matches an advisory.

NaviServer's use of OpenSSL remains in scope, including incorrect API
use, certificate or hostname verification, TLS configuration, error
handling, and object ownership or lifetime errors.

For any OpenSSL-related finding, identify the defect in NaviServer
and demonstrate how it is reachable through NaviServer.
