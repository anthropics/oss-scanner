# Nesaar — Threat Model

## Project Overview

Nesaar is a PHP-based web application for managing and displaying examination seating information for Payame Noor University. The repository includes a Dockerfile and Composer-managed PHP dependencies.

## Assets to Protect

* Examination seating assignments and related academic data.
* Student information processed or displayed by the application.
* Authentication credentials, session tokens, and application secrets.
* Database integrity and availability.
* Server filesystem, container environment, and deployment credentials.

## Trust Boundaries

* Unauthenticated users accessing public application pages.
* Authenticated users and administrative functions.
* HTTP requests and uploaded files entering the application.
* The application and its database.
* Third-party Composer packages and other build-time dependencies.
* The Docker image build process and runtime container.

## Threats to Evaluate

* Unauthorized access to student or examination data.
* Broken access control and privilege escalation.
* SQL injection and other injection vulnerabilities.
* Cross-site scripting (XSS) and cross-site request forgery (CSRF).
* Unsafe file uploads, path traversal, and arbitrary file access.
* Authentication, session-management, and password-handling weaknesses.
* Exposure of secrets, database files, temporary files, or error details.
* Vulnerable or compromised third-party dependencies.
* Insecure Docker configuration, excessive container permissions, and unsafe filesystem permissions.
* Abuse of application functionality leading to data tampering or denial of service.

## Security Assumptions and Limitations

This document describes areas to investigate; it does not assert that these vulnerabilities exist. The actual attack surface depends on the deployed configuration, enabled features, access controls, and application code.

The security review should verify whether sensitive data and secrets are excluded from the public repository and container image, whether authorization is enforced server-side, and whether database and filesystem access follow least-privilege principles.

## Intended Security Review

Assess the source code, dependency configuration, Docker build, and relevant application entry points for exploitable vulnerabilities. Findings should identify affected components, realistic attack prerequisites, potential impact, and practical remediation guidance.
