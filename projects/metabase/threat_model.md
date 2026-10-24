# Metabase threat model

## Purpose and scope

Metabase is a business intelligence and embedded analytics application for querying data sources and sharing results.
This model covers application code in the public Metabase repository, including Open Source and Enterprise code.
Features and permission controls vary by edition and configuration.

## Deployments

- **Metabase Cloud:** Metabase hosts and operates the application.
- **Self-hosted:** The deployment operator runs Metabase on infrastructure they manage.

## Assets and boundaries

Assets include connected data, query results, analytics content, application state and credentials.
The application database stores Metabase state and is separate from connected data sources.
Trust boundaries separate users and tenants, the application and external systems, and the application and its host.

Security goals are data confidentiality and integrity, enforcement of configured access boundaries, and service availability.

## Permissions

Access depends on configured data, collection and application permissions.
Public links and guest embeds use resource-specific grants.
Database operations also depend on effective database credentials and roles.

## Surfaces

- Browser UI and APIs, authentication, SSO, provisioning and API credentials.
- Query processing, database drivers, connection settings and database responses.
- Public sharing, embedding and tenant access.
- Uploads, serialization imports, Git synchronization, content rendering and exports.
- External integrations, notifications and AI/agent interfaces, including MCP.
- Administrative interfaces, background jobs, caches, plugins, custom visualizations and transforms.

## Threat actors

- Unauthenticated callers, including public-link and guest-token holders.
- Authenticated users and API clients.
- Embedded and tenant users.
- Application administrators.
- Controllers of connected data sources and external integrations.
- Infrastructure operators and software supply-chain actors.
