"""ARQ worker entry point.

Runs every piece of AI work: OCR, face matching, LLM listing analysis,
classifier inference, scoring, webhooks and maintenance. Deliberately a
separate process from the API (ADR-0003) so that ~2.5 GB of ML dependencies
and 30-second runtimes never touch the request path.

Job design rules, all of which are load-bearing:

* **Idempotent** - retries are guaranteed to happen; a job that is not
  re-runnable with the same arguments corrupts data.
* **Small payloads** - enqueue ids, never image bytes or model output.
* **Bounded** - every job has `max_tries` and a timeout. Exhausted jobs land
  in `job_runs` as DEAD and are surfaced in the admin panel; silent job loss
  is unacceptable when the outcome decides someone's trust score.
* **Traced** - the originating `request_id` propagates into the job's log
  context, so a seller-reported problem can be followed end to end.
"""

from __future__ import annotations

import time
from typing import Any

from arq import cron, func
from arq.connections import RedisSettings

from trustlens.ai.factory import (
    build_face_matcher,
    build_llm_analyzer,
    build_ocr_engine,
    build_scam_classifier,
)
from trustlens.db.session import create_engine, create_session_factory
from trustlens.db.unit_of_work import SqlAlchemyUnitOfWork
from trustlens.shared.cache import RedisCache
from trustlens.shared.clock import SystemClock, Uuid7Generator
from trustlens.shared.config.settings import get_settings
from trustlens.shared.crypto import EnvelopeEncryptor, PepperedTokenHasher
from trustlens.shared.ip import build_ip_intelligence
from trustlens.shared.logging import configure_logging, get_logger, request_id_var
from trustlens.shared.notifications import build_email_sender, build_sms_sender
from trustlens.shared.queue import ArqJobQueue
from trustlens.shared.storage import build_storage
from trustlens_worker.jobs import identity, listings, maintenance, notifications, scoring

log = get_logger(__name__)


async def startup(ctx: dict[str, Any]) -> None:
    settings = get_settings()
    configure_logging(
        level=settings.log_level,
        fmt=settings.log_format,
        service="trustlens-worker",
        version=settings.app_version,
        env=settings.env.value,
    )

    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)

    ctx["settings"] = settings
    ctx["engine"] = engine
    ctx["session_factory"] = session_factory
    ctx["uow"] = lambda: SqlAlchemyUnitOfWork(session_factory)
    ctx["cache"] = RedisCache.from_url(settings.redis.redis_url)
    ctx["queue"] = await ArqJobQueue.connect(settings.redis.redis_queue_url)
    ctx["storage"] = build_storage(settings.storage)
    ctx["clock"] = SystemClock()
    ctx["ids"] = Uuid7Generator()
    ctx["email"] = build_email_sender(settings.notifications, web_base_url=settings.web_base_url)
    ctx["sms"] = build_sms_sender(settings.notifications)
    ctx["ip_intel"] = build_ip_intelligence(settings.ip_intel)
    ctx["encryptor"] = EnvelopeEncryptor(
        settings.security.aes_key(), settings.security.encryption_key_id
    )
    ctx["hasher"] = PepperedTokenHasher(settings.security.token_pepper.get_secret_value().encode())

    # Built once and reused: the OCR reader and the face model load weights on
    # construction, which is far too expensive to repeat per job.
    ctx["ocr"] = build_ocr_engine(settings.ai)
    ctx["face"] = build_face_matcher(settings.ai)
    ctx["llm"] = build_llm_analyzer(settings.ai)
    ctx["classifier"] = build_scam_classifier(settings.ai)

    log.info("worker_started", fake_ai=settings.ai.use_fake_ai)


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["cache"].close()
    await ctx["queue"].close()
    await ctx["engine"].dispose()
    log.info("worker_stopped")


async def on_job_start(ctx: dict[str, Any]) -> None:
    ctx["_started_at"] = time.perf_counter()
    # Propagate the originating request id so a job's logs join up with the
    # HTTP request that queued it.
    request_id_var.set(str(ctx.get("job_id", "")))
    log.info("job_started", job=ctx.get("job_try"), name=ctx.get("enqueue_time"))


async def on_job_end(ctx: dict[str, Any]) -> None:
    started = ctx.get("_started_at")
    if started is not None:
        log.info("job_finished", duration_ms=round((time.perf_counter() - started) * 1000, 2))


class WorkerSettings:
    """ARQ configuration. Referenced as `arq trustlens_worker.main.WorkerSettings`."""

    # Registered under the SAME namespaced names the use cases enqueue.
    #
    # ARQ names a job after the Python function unless told otherwise, while
    # the domain enqueues by string - `identity.verify`, `contact.send_otp_sms`
    # - because it must not import the worker (ADR-0003). Left to the default,
    # not one name matched: every job was accepted by Redis and then dropped
    # with "function not found", so OCR, face matching, emails, OTP SMS and
    # rescoring silently never ran. The strings below are the contract; change
    # one only together with its caller.
    functions = [
        func(identity.verify_identity, name="identity.verify"),
        func(listings.analyse_listing, name="listings.analyse_listing"),
        func(scoring.recompute_trust_score, name="scoring.recompute_trust_score"),
        func(scoring.bulk_recompute_for_model, name="scoring.bulk_recompute_for_model"),
        func(notifications.send_email, name="notifications.send_email"),
        func(notifications.send_otp_sms, name="contact.send_otp_sms"),
        func(notifications.send_security_alert, name="notifications.send_security_alert"),
        func(maintenance.enrich_ip, name="network.enrich_ip"),
        func(maintenance.lookup_phone, name="contact.lookup_phone"),
        func(maintenance.purge_expired_media, name="maintenance.purge_expired_media"),
        func(maintenance.publish_outbox, name="maintenance.publish_outbox"),
    ]

    cron_jobs = [
        # Nightly staleness sweep: scores expire after 30 days, so sellers
        # nobody has touched still get re-evaluated.
        cron(scoring.rescore_stale_sellers, hour=3, minute=0),
        # CNIC and selfie images are purged 90 days after a terminal decision.
        # Derived hashes and scores survive, so explainability is preserved.
        cron(maintenance.purge_expired_media, hour=4, minute=0),
        # The transactional outbox relay. Frequent, because a delayed webhook
        # is a partner integration that looks broken.
        cron(maintenance.publish_outbox, second={0, 15, 30, 45}),
    ]

    on_startup = startup
    on_shutdown = shutdown
    on_job_start = on_job_start
    on_job_end = on_job_end

    redis_settings = RedisSettings.from_dsn(get_settings().redis.redis_queue_url)
    max_jobs = get_settings().worker.worker_concurrency
    job_timeout = get_settings().worker.job_default_timeout_seconds
    max_tries = get_settings().worker.job_max_tries
    # Restart after N jobs: the ML libraries are not always tidy about
    # releasing tensors, and a bounded lifetime is cheaper than chasing leaks.
    max_burst_jobs = -1
    keep_result = 3600
    health_check_interval = 30


__all__ = ["WorkerSettings"]
