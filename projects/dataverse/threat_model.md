# Threat model

## What this project does and where untrusted input enters

Dataverse is software for hosting, managing, and sharing research data. Treat
requests to its web UI and APIs, dataset metadata, uploaded files, and imported
content as potentially untrusted. Consider the security boundaries between
anonymous users, authenticated users, and users with different permissions.

## Components that matter most / least

Prioritize code paths that handle authentication and authorization, access to
restricted datasets and files, metadata and file ingestion, and API or UI
request handling. Include relevant dependencies and shared code when a
vulnerability affects Dataverse's behavior.

Do not treat a deployment-specific issue as a product vulnerability without
stating the required deployment configuration and attacker prerequisites.
There are no blanket exclusions for repository code.

## How to exercise it

Build the project and use available unit tests and repository fixtures where
appropriate. State clearly when a finding requires a deployed application,
external service, or special configuration that is not present in the build
container.

## How you rate severity

Rate severity based on realistic impact, attacker access, required privileges,
and affected configuration. Give particular weight to unauthorized access to
restricted research data, privilege escalation, data modification, and remote
code execution. Distinguish unauthenticated from authenticated attack paths,
and explain the affected roles and prerequisites. Do not assign a severity
based only on a theoretical weakness without a plausible impact.

## Anything to leave alone

Do not report a finding solely because an operator could misconfigure an
installation. If a finding depends on configuration, identify that
configuration and explain why it creates an exploitable product-level risk.
