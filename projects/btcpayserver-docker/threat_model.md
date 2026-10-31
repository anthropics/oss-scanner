# BTCPay Server Docker threat model

BTCPay Server Docker is the supported deployment and lifecycle tooling for self-hosted BTCPay Server installations. It generates Docker Compose configurations and provides privileged shell scripts for installation, updates, routing, backup, restore, and administration. Operators commonly run these scripts as root on Internet-facing hosts that hold payment metadata, credentials, and Bitcoin or Lightning node state.

## Scope and priorities

Prioritize vulnerabilities in the repository's shell scripts, `docker-compose-generator/`, `docker-compose-generator/docker-fragments/`, `nginx/`, generated Compose definitions, and installation or update workflows, especially:

- Shell, command, environment-file, Compose, or configuration injection across trust boundaries.
- Unsafe parsing or persistence of domains, environment variables, fragment names, paths, URLs, and other configuration values.
- Nginx routing, TLS termination, port exposure, authentication boundaries, and accidental publication of internal services.
- Generation, permissions, use, logging, backup, migration, and restoration of secrets and wallet or Lightning state.
- Archive traversal, symlink handling, unsafe overwrite, partial-failure behavior, and confidentiality or integrity failures in backup and restore.
- Update and supply-chain behavior, including source provenance, image references, tags, downloaded scripts, and preservation of secure configuration.
- Privilege boundaries between containers and the host, including mounted sockets, files, SSH credentials, and Docker volumes.

The Compose generator's source and generated output are both in scope. Third-party services are in scope only for how this repository configures, exposes, or integrates them; vulnerabilities solely inside an upstream container image should be reported to that upstream project. Documentation and tests may explain intended behavior or support a reproducer.

## Attackers and trust boundaries

The host administrator and a user already authorized to execute arbitrary root commands or control the Docker daemon are trusted for those intended powers. Do not report that such an operator can edit scripts, set arbitrary process environment, or replace images without demonstrating a less-privileged input path or an unintended security consequence.

Treat Internet traffic, domain and HTTP data, remotely retrieved content, backup archives, imported configuration, plugin or fragment inputs from outside the trusted base repository, and values crossing from BTCPay's web application or another container into host tooling as potentially adversarial. Configuration entered directly by an administrator can still expose other users or secrets if ordinary documented values are rendered unsafely.

Containers, the Docker daemon, the host filesystem, reverse proxy, BTCPay Server, databases, Bitcoin nodes, and Lightning nodes are distinct trust boundaries. A finding should identify which actor can supply the malicious value and what additional privilege, data, host access, or service exposure results.

## Build and offline reproduction

The scanner image contains the complete source tree, Bash and common system utilities, .NET 10, restored NuGet packages, and a Debug build of the Docker Compose generator. Run `btcpayserver-docker-oss-test` from `/src` to execute the prepared daemon-independent regression tests without network access.

The full installation test and tests that invoke real Docker Compose services require a Docker daemon and external container images, which are not provided inside the scanner. Prefer the repository's existing mock-based shell-test style for reproducers. The Compose generator can be exercised from its built output without downloading packages. Do not require Internet access or real funds, keys, domains, or production hosts.

## Findings, severity, and patches

Prioritize remotely reachable host command execution, compromise of the Docker host or daemon, theft or corruption of wallet or Lightning secrets, malicious backup restoration that escapes its destination, and default exposure of sensitive internal services. Rate issues according to the actual attacker-controlled input, required operator action, default configuration, affected assets, and reliability. A dangerous result that requires a trusted root operator to deliberately supply arbitrary shell syntax is not by itself an injection vulnerability.

For each report, include the affected commit and source locations, deployment configuration, trust boundary, exact input path, a safe self-contained reproducer, expected versus observed behavior, and concrete impact. Prefer a focused regression test using mocked Docker commands and temporary directories, plus a minimal candidate patch. Group findings sharing one root cause and distinguish repository-owned configuration flaws from vulnerabilities in upstream images.

Send reports only to the configured security contact. Do not open public issues or publish unpatched reproduction details.
