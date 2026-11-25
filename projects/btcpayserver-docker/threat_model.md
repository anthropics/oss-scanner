# BTCPay Server Docker threat model

BTCPay Server Docker is the supported deployment and lifecycle tooling for self-hosted BTCPay Server installations. It generates Docker Compose configurations and provides privileged shell scripts for installation, updates, routing, backup, restore, and administration. Operators commonly run these scripts as root on Internet-facing hosts that hold payment metadata, credentials, and Bitcoin or Lightning node state.

## Scope and priorities

Prioritize vulnerabilities exploitable without pre-existing attacker access to the deployment host in the repository's shell scripts, `docker-compose-generator/`, `docker-compose-generator/docker-fragments/`, `nginx/`, generated Compose definitions, and installation or update workflows, especially:

- Shell, command, environment-file, Compose, or configuration injection across trust boundaries.
- Unsafe parsing or persistence of domains, environment variables, fragment names, paths, URLs, and other configuration values.
- Nginx routing, TLS termination, port exposure, authentication boundaries, and accidental publication of internal services.
- Generation, permissions, use, logging, backup, migration, and restoration of secrets and wallet or Lightning state.
- Archive traversal, symlink handling, unsafe overwrite, partial-failure behavior, and confidentiality or integrity failures in backup and restore.
- Update and supply-chain behavior, including source provenance, image references, tags, downloaded scripts, and preservation of secure configuration.
- Privilege boundaries between containers and the host, including mounted sockets, files, SSH credentials, and Docker volumes.

The Compose generator's source and generated output are both in scope. Third-party services are in scope only for how this repository configures, exposes, or integrates them; vulnerabilities solely inside an upstream container image should be reported to that upstream project. Documentation and tests may explain intended behavior or support a reproducer.

## Attackers and trust boundaries

The official `btcpayserver/btcpayserver-docker` repository and its maintained contents are trusted, including its scripts, Compose generator, Docker fragments, and update code. Findings that require malicious repository contents, compromised maintainers or repository write access, or an operator installing or updating from an attacker-controlled fork or replacement repository are out of scope. Do not model repository-provided scripts or fragments as untrusted input that must be sandboxed. This does not exclude vulnerabilities in trusted code when processing genuinely attacker-controlled external input, or flaws that let an external attacker substitute code without first controlling the trusted repository or host.

The deployment host is trusted. Defending against an attacker who already has access to the host is not a security goal, including an attacker with an unprivileged local account or local code execution. Local privilege escalation and attacks requiring the attacker to create or modify host files, directories, symlinks, scripts, configuration, process environment, or local command lookup are out of scope. This includes planting files or symlinks for a privileged installation, update, backup, or restore script to consume. Do not assume an untrusted local user shares the deployment host.

The host administrator and users authorized to control the Docker daemon are trusted for those intended powers. Their ability to edit scripts, set arbitrary process environment, choose configuration or fragments, or replace images is not a vulnerability.

Treat Internet traffic, domain and HTTP data, remotely retrieved content, backup archives, imported configuration, plugin or fragment inputs from outside the trusted base repository, and values crossing from BTCPay's web application or another container into host tooling as potentially adversarial when an attacker can supply them without existing host access. For example, an operator restoring an externally supplied backup can be an in-scope input path; an attacker first planting a malicious archive or symlink on the host is not. Configuration entered directly by an administrator can still expose other users or secrets if ordinary documented values are rendered unsafely.

Containers, the Docker daemon, the host filesystem, reverse proxy, BTCPay Server, databases, Bitcoin nodes, and Lightning nodes are distinct trust boundaries. Remote attacks that gain host access, including through a remotely compromised service container, remain in scope; the host-access exclusion must not be used to dismiss the resulting host compromise. A finding should identify which actor can supply the malicious value, how they do so without pre-existing host access, and what additional privilege, data, host access, or service exposure results.

## Build and offline reproduction

The scanner image contains the complete source tree, Bash and common system utilities, .NET 10, restored NuGet packages, and a Debug build of the Docker Compose generator. Run `btcpayserver-docker-oss-test` from `/src` to execute the prepared daemon-independent regression tests without network access.

The full installation test and tests that invoke real Docker Compose services require a Docker daemon and external container images, which are not provided inside the scanner. Prefer the repository's existing mock-based shell-test style for reproducers. The Compose generator can be exercised from its built output without downloading packages. Do not require Internet access or real funds, keys, domains, or production hosts.

## Findings, severity, and patches

Prioritize remotely reachable host command execution, compromise of the Docker host or daemon, theft or corruption of wallet or Lightning secrets, malicious backup restoration that escapes its destination, and default exposure of sensitive internal services, subject to the host-access and trusted-repository exclusions above. Rate issues according to the actual attacker-controlled input, required operator action, default configuration, affected assets, and reliability. A dangerous result that requires a trusted root operator to deliberately supply arbitrary shell syntax is not by itself an injection vulnerability. Findings whose exploit prerequisites include existing attacker access to the host or a malicious repository are out of scope, not merely lower severity.

For each report, include the affected commit and source locations, deployment configuration, trust boundary, exact input path, a safe self-contained reproducer, expected versus observed behavior, and concrete impact. Prefer a focused regression test using mocked Docker commands and temporary directories, plus a minimal candidate patch. Group findings sharing one root cause and distinguish repository-owned configuration flaws from vulnerabilities in upstream images.

Send reports only to the configured security contact. Do not open public issues or publish unpatched reproduction details.
