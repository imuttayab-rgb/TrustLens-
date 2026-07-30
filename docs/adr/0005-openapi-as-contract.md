# ADR-0005: OpenAPI is the single source of truth for the frontend contract

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Haseeb Ur Rehman, Muhammad Muttayab

## Context

The frontend is TypeScript and the backend is Python. In split-stack student projects, the dominant
source of integration bugs is a hand-maintained duplicate of the API's types on the client, which drifts
silently until something breaks in a demo.

## Decision

FastAPI's generated `/openapi.json` is the contract. `pnpm codegen` runs `openapi-typescript` +
`openapi-fetch` to produce `packages/api-client` (types + a typed client). CI regenerates and **fails the
build if the committed output differs** from a fresh generation.

Consequence by design: a backend field rename breaks the **frontend type-check in the same PR**.

## Alternatives considered

| Option | Why rejected |
|---|---|
| **Hand-written TS types and fetch wrappers** | Guaranteed drift. The failure mode is a runtime `undefined` in front of an examiner, not a compile error |
| **tRPC** | Requires a TypeScript backend; the proposal mandates FastAPI |
| **GraphQL** | Adds a schema layer, a client cache, and N+1 concerns to solve a problem that generated REST types already solve. Also a poor fit for the partner-facing public API, where REST + API keys is what integrators expect |
| **Protobuf / gRPC** | Strong typing, but browser support requires a proxy, and it forfeits the human-readable REST surface the public API needs |
| **Generate the backend from a hand-written OpenAPI spec** (spec-first) | Cleaner in theory, but fights FastAPI, whose value is that the spec falls out of typed Python |

## Consequences

**Positive**
- One definition of every request and response shape.
- Breaking changes surface at build time, in the PR that caused them.
- Swagger UI, ReDoc, and the Postman collection (a proposal-listed tool) all come from the same document.
- Schemathesis can fuzz the API directly from the spec ([14 §5](../14-testing-strategy.md)).

**Negative / accepted costs**
- `pnpm codegen` must be run after any API change; forgetting it fails CI (which is the intended
  behaviour, but is friction).
- Generated code is committed, so PR diffs include generated files. Mitigated by marking them
  `linguist-generated` in `.gitattributes` so reviews collapse them.
- The quality of the generated types depends on the quality of the Pydantic models — sloppy `dict[str, Any]`
  response models produce useless client types. This is a standards issue, covered in
  [13](../13-coding-standards.md).

**Revisit if:** the project ever moves to a TypeScript backend, at which point tRPC would remove the
generation step entirely.
