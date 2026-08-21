# ADR-0004: Framework-free domain package with ports and adapters

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Haseeb Ur Rehman, Muhammad Muttayab

## Context

Two processes (`apps/api` and `apps/worker`) must execute the same business logic — computing a trust
score happens both from an admin HTTP request and from a background job. The system integrates six
swappable external dependencies (OpenAI/Claude, EasyOCR, DeepFace, the classifier, IP intelligence,
SMS/email), and the scoring rules must be exhaustively testable because they decide whether a real person
is labelled a fraud risk.

## Decision

`packages/py/trustlens-core` contains entities, value objects, policies, use cases, and **ports**
(`typing.Protocol` interfaces), importing nothing beyond the standard library and Pydantic. Adapter
packages (`trustlens-db`, `trustlens-ai`, `trustlens-shared`) implement the ports. `apps/api` and
`apps/worker` are composition roots that wire adapters into use cases.

The dependency rules are enforced in CI by `import-linter`, not by convention:
`trustlens-core` may not import `sqlalchemy`, `fastapi`, `arq`, `openai`, `anthropic`, `cv2`, or `redis`;
adapters may not import each other; packages may not import apps.

## Alternatives considered

| Option                                                                    | Why rejected                                                                                                                                                                              |
| ------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Standard FastAPI layout** (routers → services → SQLAlchemy models)      | Business logic ends up coupled to the ORM and the request object. The worker would have to import FastAPI machinery to reuse a service, and unit-testing scoring would require a database |
| **Anaemic services over ORM models**                                      | Rules scatter across services and route handlers; nobody can point at "the scoring logic"                                                                                                 |
| **Full hexagonal architecture with strict DTO mapping at every boundary** | More ceremony than a 2-person FYP can sustain; the chosen design keeps repositories returning domain entities but allows read models to bypass them (CQRS-lite)                           |
| **Abstract base classes instead of Protocols**                            | Forces adapters to inherit from a core class, creating a compile-time dependency in the wrong direction. Protocols give structural typing with no inheritance link                        |

## Consequences

**Positive**

- The same use case runs identically from HTTP, a job, or a test.
- Scoring policies are pure functions of their inputs — 95% coverage is achievable and meaningful.
- Swapping OpenAI for Claude, or EasyOCR for a cloud OCR, is a one-file change.
- Later extraction of a service is mechanical: reimplement a port over HTTP; the domain does not change.
- The `Clock` and `IdGenerator` ports make time- and id-dependent logic deterministically testable.

**Negative / accepted costs**

- More files and more indirection than a conventional FastAPI app. A newcomer needs the layering
  explained before the codebase reads naturally — hence [03](../03-backend-architecture.md).
- Mapping between ORM rows and domain entities is boilerplate at the repository edge.
- Requires discipline; the `import-linter` contracts exist because discipline alone is not reliable.

**Revisit if:** the indirection is measurably slowing delivery on simple CRUD features. The likely
adjustment is to allow trivial read paths to bypass use cases (already permitted for `queries/`), not to
abandon the layering for the scoring core.
