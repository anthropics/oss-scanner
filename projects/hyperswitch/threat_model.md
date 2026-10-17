# Hyperswitch Security Threat Model

## Overview

Hyperswitch is an open-source payment orchestration platform
developed by Juspay, primarily implemented in Rust.

The platform connects merchants to payment processors, vault
providers, fraud providers, and other financial infrastructure.

## Security Objectives

The scanner should prioritize vulnerabilities that could:

1. Enable unauthorized financial transactions.
2. Expose sensitive payment credentials or customer data.
3. Bypass authentication or authorization.
4. Compromise isolation between merchants or organizations.
5. Manipulate payment states or transaction amounts.
6. Enable unauthorized access to payment tokens.
7. Compromise payment processor integrations.

## Critical Security Areas

### Authentication and Authorization

- API key authentication
- JWT validation
- Role-based access control
- Administrative API access
- Merchant and organization authorization
- Privilege escalation

### Payment Processing

- Payment authorization and capture
- Refunds and reversals
- Payment state transitions
- Idempotency and replay protection
- Transaction amount manipulation
- Race conditions and duplicate transactions

### Multi-Tenant Security

- Cross-merchant data access
- Organization and merchant isolation
- Customer and payment method ownership
- Platform merchant access controls

### Vault and Tokenization

- Sensitive payment data handling
- Payment method token authorization
- Network tokenization
- External vault integrations
- Credential exposure

### Connector Integrations

- Server-side request forgery
- Connector credential exposure
- Untrusted processor responses
- Webhook signature verification
- Webhook replay protection

### Infrastructure and Data

- SQL injection
- Sensitive data exposure through logs
- Redis-backed authentication and session state
- Secret management
- Cryptographic vulnerabilities

## Trust Boundaries

- Merchant applications to Hyperswitch APIs
- Administrative users to privileged APIs
- Hyperswitch to payment processors
- Hyperswitch to vault providers
- External providers to webhook endpoints
- Hyperswitch to databases and caches
- Organizations and merchants sharing infrastructure

## Vulnerability Severity

### Critical

- Unauthorized financial operations at scale
- Administrative authentication bypass
- Widespread cross-merchant data exposure
- Unauthenticated exposure of sensitive cardholder data
- Remote code execution with significant security impact

### High

- Unauthorized payment or refund manipulation
- Cross-merchant authorization bypass
- Sensitive credential exposure
- Exploitable webhook authentication bypass
- Injection vulnerabilities with significant security impact

### Medium

- Limited information disclosure
- Authorization weaknesses with constrained impact
- Exploitable denial of service with limited impact

### Low

- Minor information disclosure
- Security hardening opportunities without demonstrated impact

Severity should be assessed using exploitability,
required privileges, affected assets, and financial impact.

## Reporting Expectations

Findings should include:

1. Affected component and source code location
2. Vulnerability description and root cause
3. Exploitation prerequisites
4. Reproduction steps
5. Demonstrated security impact
6. Suggested remediation

Use synthetic test data for reproductions.

Do not assume access to production infrastructure,
private merchant credentials, or real payment data.
