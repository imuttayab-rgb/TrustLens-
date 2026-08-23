# Multi-Factor Authentication (MFA) - Future Scope

## Overview
As part of the system's security architecture, Multi-Factor Authentication (MFA) was considered for protecting high-privilege accounts (such as Administrators and Reviewers) and sensitive seller profiles. 

## Implementation Decision
During the development phase, a strategic decision was made to defer the implementation of MFA to the future scope. The rationale for this decision is as follows:

1. **Scope Management for FYP:** TrustLens has a broad surface area, incorporating AI-driven trust scoring, identity verification workflows, duplicate listing detection, and a full-stack microservices architecture. Fully implementing a robust MFA system (including TOTP generation, backup codes, and recovery workflows) would have diverted significant development time away from the core AI and trust-scoring objectives.
2. **Current Security Controls:** The system already implements strict security measures, including rate-limiting (per-IP and per-account), secure HttpOnly refresh tokens, password complexity policies, and session revocation capabilities. These controls sufficiently mitigate brute-force and session-hijacking risks for the initial deployment.
3. **Future Extension:** The database schema (`User` model) already includes an `mfa_enabled` flag, and the authentication domain logic has been architected to accommodate MFA enforcement rules (e.g., `SECURITY_MFA_REQUIRED_ROLES`). This ensures that when MFA is developed in the future, the foundational architecture is already prepared to support it without requiring major refactoring.

## Conclusion
MFA remains a critical enhancement for a production-scale marketplace, particularly for administrative access. It is formally documented as a planned feature for subsequent iterations of the TrustLens platform.
