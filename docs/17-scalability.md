# 17 — Scalability

The architecture is deliberately sized for an FYP but shaped so that growth is a sequence of local
changes rather than a rewrite. This document states what changes at each stage of load, and — as
importantly — what should _not_ be built yet.

## 1. Current sizing

| Dimension              | Design target                 |
| ---------------------- | ----------------------------- |
| Sellers                | 10k                           |
| Public score reads     | 100 req/s sustained           |
| Identity verifications | 500/day                       |
| Listing analyses       | 5k/day                        |
| API partners           | 10                            |
| Instances              | 1–3 API replicas, 1–2 workers |

## 2. Growth path

| Stage | Trigger                       | Change                                                                                                      | Cost   |
| ----- | ----------------------------- | ----------------------------------------------------------------------------------------------------------- | ------ |
| 1     | Baseline                      | 1 API, 1 worker, managed PG + Redis                                                                         | —      |
| 2     | CPU > 70%                     | Scale API replicas horizontally (already stateless)                                                         | Config |
| 3     | Queue depth > 100             | Scale workers; split queues by priority (identity > listing > maintenance)                                  | Config |
| 4     | Read-heavy admin queries slow | Postgres read replica; route `queries/` read models to it                                                   | Small  |
| 5     | Public API dominates traffic  | CDN in front of `/public/v1` using the existing `Cache-Control`/`ETag`                                      | Small  |
| 6     | ML jobs starve other work     | Extract `apps/worker` ML jobs into a dedicated GPU/high-memory worker service consuming its own queue       | Medium |
| 7     | Postgres write-bound          | Partition `access_events`/`api_request_logs`/`audit_logs` (already designed); move analytics to a warehouse | Medium |
| 8     | Team or domain grows          | Extract a bounded context into a service using the existing ports                                           | Large  |

Nothing before stage 6 requires touching application code — the horizontal steps were paid for upfront by
statelessness, the queue, and the cache.

## 3. Why the current design scales horizontally

| Property                                               | Consequence                                               |
| ------------------------------------------------------ | --------------------------------------------------------- |
| API is **stateless** (no server sessions; JWT + Redis) | Add replicas freely                                       |
| Heavy work is **queued**                               | Load spikes lengthen the queue, they don't fail requests  |
| Jobs are **idempotent**                                | Retries and at-least-once delivery are safe               |
| Reads are **cached**                                   | Partner traffic barely touches the database               |
| Scores are **precomputed**                             | The read path is a key lookup, not a computation          |
| DB access is **pooled and bounded**                    | Adding replicas can't exhaust `max_connections` unnoticed |
| Domain is **framework-free**                           | Extraction to a service doesn't touch business logic      |

## 4. Caching layers

| Layer       | What                                                               | Where                                          |
| ----------- | ------------------------------------------------------------------ | ---------------------------------------------- |
| Browser/CDN | Static assets, public score pages (ISR)                            | Vercel edge                                    |
| Application | Score payloads, seller summaries, IP intel, disposable-domain list | Redis                                          |
| Query       | Read models for admin dashboards                                   | Postgres materialised views, refreshed by cron |
| Model       | Loaded classifier artifacts, DeepFace weights                      | Worker process memory                          |

Growth levers, in order of value: raise the score TTL (300 s → 900 s) since scores change rarely; add a
CDN in front of the public API; precompute the public payload as `JSONB` on the score row so a cache miss
is a single-row read with no joins.

## 5. Queues and background jobs

Already in place: ARQ over Redis, retries with backoff, dead-letter visibility, cron jobs, per-seller
debounce and locking.

At scale:

- **Priority queues** — `critical` (identity, OTP), `default` (scoring, listing analysis), `low`
  (maintenance, webhooks). A backlog of listing analyses must never delay a seller's OTP.
- **Dedicated ML workers** with more memory and, if warranted, a GPU. The queue split is the seam.
- **Batching** — group listing analyses per seller into one LLM call to cut per-request overhead and cost.
- **Redis Streams or a broker** if at-least-once delivery guarantees need to be stronger than ARQ's;
  the `JobQueue` port means this is one adapter.

## 6. Database scaling

Already designed in: UUIDv7 for index locality · partitioning on the three append-only tables · indexes
sized to the actual query patterns ([05 §5](05-database-design.md)) · read models separate from
aggregate repositories (CQRS-lite) · statement timeouts.

Next steps by symptom:

| Symptom                       | Action                                                              |
| ----------------------------- | ------------------------------------------------------------------- |
| Admin dashboards slow         | Materialised views refreshed on a schedule                          |
| Reads dominate                | Read replica; `queries/` routed to it (writes stay on the primary)  |
| Append-only tables huge       | Drop old partitions; archive to object storage                      |
| Connection pressure           | PgBouncer in transaction mode                                       |
| Analytics competing with OLTP | Nightly export to a warehouse; stop querying production for reports |

Sharding is explicitly **not** planned. It would be justified only far beyond any realistic scale for this
system, and it forecloses cross-seller queries (device clustering, duplicate CNIC detection) that are core
to the product.

## 7. Adding new capability without redesign

| New requirement                      | Change needed                                                                                 |
| ------------------------------------ | --------------------------------------------------------------------------------------------- |
| A new scoring signal                 | Seed a `signal_definitions` row + a collector + a weight. **The scoring policy is untouched** |
| A new AI provider                    | One adapter implementing the existing port; passes the same contract tests                    |
| A new document type (passport)       | New `document_type` enum value + a parser; the pipeline is unchanged                          |
| Reverse-image stolen-photo detection | `perceptual_hash` is already stored; add a similarity index + a signal                        |
| Reputation history                   | `trust_scores` is already append-only — this is a read model, not a schema change             |
| Chat scam detection                  | New entity + analyser + signal; the same LLM port                                             |
| Direct marketplace integration       | Webhooks and API-key infrastructure already exist; add an ingestion adapter                   |
| Mobile app                           | The API is already the only backend; add a client                                             |

Each of these is a _localised_ change precisely because signals are data, providers are ports, and scores
are append-only. That is the payoff for the upfront structure.

## 8. Microservice extraction (only if genuinely needed)

The order of extraction, easiest and highest-value first:

1. **ML/AI service** — heaviest dependencies, most independent scaling profile, cleanest port boundary
   (`OcrEngine`, `FaceMatcher`, `LlmAnalyzer`, `ScamClassifier`).
2. **Public API service** — different availability and rate-limit profile from the internal API; read-only.
3. **Scoring service** — only if scoring becomes computationally heavy (e.g. graph-based fraud rings).

Extraction is mechanical: implement the existing port over HTTP/gRPC, swap the adapter in the container,
deploy. `trustlens-core` does not change. That is the whole point of the port structure.

**Do not extract** for organisational reasons alone at this size. Two students with three services get
distributed-system failure modes and zero of the benefits.

## 9. Observability at scale

Add before you need it, not after: RED metrics (rate/errors/duration) per endpoint, queue depth and job
duration per job type, cache hit ratio, AI cost and latency per provider, per-signal availability rates,
score distribution over time.

**Score distribution drift is the highest-value business metric** in this system: a sudden shift in the
proportion of HIGH-risk sellers almost always means a model regression, a provider outage, or a bad weight
change — not a sudden influx of scammers. Alerting on it catches problems that no technical metric shows.

## 10. What we are deliberately NOT building yet

| Not building            | Why                                                                                      |
| ----------------------- | ---------------------------------------------------------------------------------------- |
| Kubernetes              | Railway covers this scale; K8s adds an operations burden two students shouldn't carry    |
| Service mesh            | No services to mesh                                                                      |
| Event streaming (Kafka) | The transactional outbox + Redis covers current volume; Kafka's operational cost is real |
| GraphQL                 | REST + generated types already gives typed, evolvable contracts                          |
| Multi-region            | Single region matches the target market; adds replication complexity                     |
| Feature-flag service    | Env vars and a config table suffice at this size                                         |
| Custom auth provider    | Standard JWT + RBAC is well understood and auditable                                     |
| Real-time WebSockets    | Polling/SSE is sufficient for job progress                                               |

Every line here is a decision **not** to spend the FYP's limited time on infrastructure that would not
change the outcome. Each one has a documented trigger for revisiting it.
