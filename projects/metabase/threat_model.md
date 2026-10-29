# Metabase Open Source Edition threat model

## Purpose and scope

Metabase is a business intelligence and embedded analytics application for querying data sources and sharing results.
This enrollment covers AGPL-licensed Open Source Edition source code.
The top-level `enterprise/` directory is outside the scan scope.

## Deployments

- **Metabase Cloud:** Metabase hosts and operates the application.
- **Self-hosted:** The deployment operator runs Metabase on infrastructure they manage.

## Assets and boundaries

Assets include connected data, query results, analytics content, application state and credentials.
The application database stores Metabase state and is separate from connected data sources.
Trust boundaries separate users and permission groups, the application and external systems, and the application and its host.

Security goals are data confidentiality and integrity, enforcement of configured access boundaries, and service availability.

## Permissions

Access depends on configured data, collection and application permissions.
Public links and guest embeds use resource-specific grants.
Database operations also depend on effective database credentials and roles.

## Surfaces

- Browser UI and APIs, authentication, sessions and API credentials.
- Query processing, database drivers, connection settings and database responses.
- Public sharing and embedding.
- Uploads, content rendering and exports.
- Notifications, subscriptions and external integrations.
- Administrative interfaces, background jobs, caches and plugins.

## Threat actors

- Unauthenticated callers, including public-link and guest-token holders.
- Authenticated users and API clients.
- Embedded users.
- Application administrators.
- Controllers of connected data sources and external integrations.
- Infrastructure operators and software supply-chain actors.
