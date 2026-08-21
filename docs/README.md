# TrustLens Documentation

Start with [`../ARCHITECTURE.md`](../ARCHITECTURE.md) for the 5-minute overview, then read in order.

## Foundations

1. [Project Overview](01-project-overview.md) — what we're building and why, traced to the proposal
2. [System Architecture](02-system-architecture.md) — containers, runtime flows, technology choices

## Design

3. [Backend Architecture](03-backend-architecture.md)
4. [Frontend Architecture](04-frontend-architecture.md)
5. [Database Design](05-database-design.md)
6. [API Design](06-api-design.md)
7. [Authentication & Authorization](07-authentication-authorization.md)
8. [Trust Score Engine](08-trust-score-engine.md)
9. [User Roles](09-user-roles.md)

## Engineering

10. [Folder Structure Guide](10-folder-structure.md)
11. [Development Setup](11-development-setup.md)
12. [Environment Variables](12-environment-variables.md)
13. [Coding Standards](13-coding-standards.md)
14. [Testing Strategy](14-testing-strategy.md)
15. [Security](15-security.md)
16. [Deployment Guide](16-deployment.md)
17. [Scalability](17-scalability.md)
18. [Contribution Guide](18-contributing.md)
19. [Future Improvements](19-future-improvements.md)

## Decision records

- [ADR index](adr/README.md)

## Conventions used in these docs

- **MUST / SHOULD / MAY** follow RFC 2119.
- Blocks marked **> ASSUMPTION** record something the proposal did not specify. Every one is listed in
  [01 §7](01-project-overview.md#7-assumptions-register). If a supervisor rules differently, only the
  code behind that assumption changes.
- Blocks marked **> WHY** explain a decision that a reader might otherwise reverse.
