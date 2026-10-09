# Threat model

Alby Hub is a self-custodial bitcoin Lightning wallet. What we protect is the user's funds.

## Severity
- Critical: anything that lets someone other than the owner spend, move or lock up funds, or exceed what the user has
  explicitly allowed them access to, or obtain the seed or keys.
- High: unauthorized access to the hub that does not directly lead to loss of funds.
- Everything else is low priority.
