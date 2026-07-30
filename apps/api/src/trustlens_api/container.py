"""Composition root.

This is the ONLY module that knows which concrete adapter implements which
port. Everything else depends on the Protocol. Swapping OpenAI for Claude, S3
for MinIO, or a real SMS provider for the console one is a change here and
nowhere else (ADR-0004).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from trustlens.core.domain.ports import (
    Cache,
    Clock,
    EmailSender,
    IdGenerator,
    IpIntelligence,
    JobQueue,
    ObjectStorage,
    SmsSender,
)
from trustlens.db.session import create_engine, create_session_factory
from trustlens.db.unit_of_work import SqlAlchemyUnitOfWork
from trustlens.shared.cache import IdempotencyStore, RedisCache, TokenBucketLimiter
from trustlens.shared.clock import SystemClock, Uuid7Generator
from trustlens.shared.config.settings import Settings
from trustlens.shared.crypto import (
    ApiKeyFactory,
    Argon2PasswordHasher,
    EnvelopeEncryptor,
    JwtService,
    OtpCodeGenerator,
    PepperedTokenHasher,
)
from trustlens.shared.ip import build_ip_intelligence
from trustlens.shared.logging import get_logger
from trustlens.shared.notifications import build_email_sender, build_sms_sender
from trustlens.shared.queue import ArqJobQueue, NullJobQueue
from trustlens.shared.storage import build_storage

log = get_logger(__name__)


@dataclass
class Container:
    """Long-lived application dependencies, built once at startup."""

    settings: Settings
    engine: Any
    session_factory: Any
    cache: Cache
    queue: JobQueue
    storage: ObjectStorage
    clock: Clock
    ids: IdGenerator
    password_hasher: Argon2PasswordHasher
    token_hasher: PepperedTokenHasher
    otp_generator: OtpCodeGenerator
    api_keys: ApiKeyFactory
    jwt: JwtService
    encryptor: EnvelopeEncryptor
    email: EmailSender
    sms: SmsSender
    ip_intel: IpIntelligence
    rate_limiter: TokenBucketLimiter
    idempotency: IdempotencyStore

    def uow(self) -> SqlAlchemyUnitOfWork:
        """A fresh unit of work per request.

        Never shared: a UoW holds a session and a transaction, and sharing one
        across concurrent requests would interleave their writes.
        """
        return SqlAlchemyUnitOfWork(self.session_factory)


async def build_container(settings: Settings) -> Container:
    engine = create_engine(settings.database)
    session_factory = create_session_factory(engine)

    cache = RedisCache.from_url(
        settings.redis.redis_url, max_connections=settings.redis.redis_max_connections
    )

    try:
        queue: JobQueue = await ArqJobQueue.connect(settings.redis.redis_queue_url)
    except Exception as exc:
        # Degrade rather than refuse to boot: read paths (the public score
        # lookup) stay fully functional without the queue, and the API is more
        # useful up than down. Writes that need a job will surface the failure.
        log.error("job_queue_unavailable", error=str(exc), degraded=True)
        queue = NullJobQueue()

    password_hasher = Argon2PasswordHasher(settings.security)

    return Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        cache=cache,
        queue=queue,
        storage=build_storage(settings.storage),
        clock=SystemClock(),
        ids=Uuid7Generator(),
        password_hasher=password_hasher,
        token_hasher=PepperedTokenHasher(
            settings.security.token_pepper.get_secret_value().encode()
        ),
        otp_generator=OtpCodeGenerator(settings.security.otp_pepper.get_secret_value().encode()),
        api_keys=ApiKeyFactory(settings.security.api_key_prefix, password_hasher),
        jwt=JwtService(settings.security),
        encryptor=EnvelopeEncryptor(
            settings.security.aes_key(), settings.security.encryption_key_id
        ),
        email=build_email_sender(settings.notifications, web_base_url=settings.web_base_url),
        sms=build_sms_sender(settings.notifications),
        ip_intel=build_ip_intelligence(settings.ip_intel),
        rate_limiter=TokenBucketLimiter(cache),
        idempotency=IdempotencyStore(cache),
    )


async def close_container(container: Container) -> None:
    for closer in (
        getattr(container.cache, "close", None),
        getattr(container.queue, "close", None),
    ):
        if closer is not None:
            try:
                await closer()
            except Exception as exc:
                log.warning("shutdown_close_failed", error=str(exc))
    await container.engine.dispose()


__all__ = ["Container", "build_container", "close_container"]
