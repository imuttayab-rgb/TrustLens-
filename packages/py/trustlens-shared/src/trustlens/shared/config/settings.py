"""Typed configuration.

Rules this module enforces (docs/12 section 1):

1. **Fail fast** - the app refuses to start on a missing or malformed value.
   No `os.getenv(...) or "default"` anywhere.
2. **No defaults for secrets** - a default JWT key is how a development key
   reaches production.
3. Constructed **once** at startup and injected; nothing reads `os.environ`
   at call time.
4. Production asserts its own hardening (DEBUG off, no wildcard CORS, real
   secrets, TLS to the database).
"""

from __future__ import annotations

import base64
import sys
from enum import StrEnum
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import (
    BeforeValidator,
    Field,
    SecretStr,
    computed_field,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_deployed(self) -> bool:
        return self in {Environment.STAGING, Environment.PRODUCTION}


def _csv(value: str | list[str]) -> list[str]:
    """Comma-separated env values -> list, tolerating whitespace."""
    if isinstance(value, list):
        return value
    return [item.strip() for item in str(value).split(",") if item.strip()]


#: `NoDecode` is essential: without it pydantic-settings tries to JSON-parse
#: any list-typed field coming from the environment, so `a,b` fails before our
#: validator ever runs. With it, the raw string reaches `_csv`.
CsvList = Annotated[list[str], NoDecode, BeforeValidator(_csv)]


class _Base(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


class DatabaseSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    database_url: str
    database_url_sync: str
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_echo: bool = False
    db_statement_timeout_ms: int = 10_000
    db_ssl_require: bool = False

    @field_validator("database_url")
    @classmethod
    def _must_be_async(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the asyncpg driver "
                "(postgresql+asyncpg://). A sync driver blocks the event loop."
            )
        # Managed providers hand you a libpq URL, and pasting it verbatim is
        # the obvious thing to do. asyncpg does not understand `sslmode` and
        # fails at connection time with an error that names neither the
        # parameter nor the driver, so it reads as "the database is down".
        # TLS for the async engine comes from DB_SSL_REQUIRE instead.
        libpq_only = [p for p in ("sslmode=", "channel_binding=") if p in v]
        if libpq_only:
            names = " and ".join(p.rstrip("=") for p in libpq_only)
            raise ValueError(
                f"DATABASE_URL contains `{names}`, which asyncpg does not accept. "
                "Neon and most managed providers hand you a libpq string with these "
                "in it. Strip everything after the `?` for this variable and set "
                "DB_SSL_REQUIRE=true instead; keep `?sslmode=require` on "
                "DATABASE_URL_SYNC, which uses psycopg and does need it."
            )
        return v

    @field_validator("database_url_sync")
    @classmethod
    def _sync_is_sync(cls, v: str) -> str:
        if v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL_SYNC must NOT use asyncpg - Alembic runs synchronously. "
                "Use postgresql+psycopg://"
            )
        return v

    @model_validator(mode="after")
    def _tls_reaches_migrations_too(self) -> DatabaseSettings:
        """Alembic reads DATABASE_URL_SYNC verbatim; nothing injects TLS into it.

        So a remote database configured with DB_SSL_REQUIRE=true is reached
        over TLS by the app and, unless `sslmode` is in the sync URL, in
        plaintext by the migration step - or refused outright, since managed
        providers reject unencrypted connections. Either way the failure
        surfaces during a release, which is the worst time to find it.
        """
        if self.db_ssl_require and "sslmode=" not in self.database_url_sync:
            raise ValueError(
                "DB_SSL_REQUIRE is true but DATABASE_URL_SYNC has no `sslmode`. "
                "Alembic uses that URL as given, so migrations would not be encrypted. "
                "Append `?sslmode=require` to DATABASE_URL_SYNC."
            )
        return self


class RedisSettings(_Base):
    redis_url: str = "redis://localhost:6379/0"
    #: A separate DB index from the cache, so flushing the cache can never
    #: destroy queued jobs.
    redis_queue_url: str = "redis://localhost:6379/1"
    redis_max_connections: int = 20
    cache_ttl_score_seconds: int = 300
    cache_ttl_default_seconds: int = 120

    @model_validator(mode="after")
    def _queue_must_differ(self) -> RedisSettings:
        if self.redis_url == self.redis_queue_url:
            raise ValueError(
                "REDIS_URL and REDIS_QUEUE_URL must use different database indexes, "
                "otherwise a cache flush drops queued jobs."
            )
        return self


class SecuritySettings(_Base):
    model_config = SettingsConfigDict(env_prefix="security_", extra="ignore")

    jwt_private_key: SecretStr
    jwt_public_key: SecretStr
    jwt_algorithm: Literal["EdDSA", "RS256", "HS256"] = "EdDSA"
    jwt_issuer: str
    jwt_audience: str = "trustlens-web"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    refresh_idle_ttl_days: int = 7

    password_min_length: int = 12
    argon2_memory_kib: int = 65_536
    argon2_time_cost: int = 3
    argon2_parallelism: int = 4

    otp_pepper: SecretStr
    token_pepper: SecretStr
    encryption_key: SecretStr
    encryption_key_id: str = "k1"

    #: Signs public API responses (P6-04). A distinct secret from the token and
    #: OTP peppers: this one is shared with partners in the sense that they
    #: verify against it, so its blast radius must not include session tokens.
    #: Defaults to empty, in which case responses are served unsigned rather
    #: than the API refusing to boot - signing is an integrity guarantee to add,
    #: not a precondition for serving a score.
    response_signing_secret: SecretStr = SecretStr("")
    response_signing_key_id: str = "s1"
    #: How long a signed response stays verifiable. Bounded so a captured
    #: response cannot be replayed as current a month later.
    response_signature_ttl_seconds: int = 300

    api_key_prefix: str = "tl_test"
    cors_origins: CsvList = Field(default_factory=list)
    trusted_hosts: CsvList = Field(default_factory=lambda: ["localhost", "127.0.0.1"])
    #: How many X-Forwarded-For hops to trust. Too high and any client can
    #: spoof its IP, defeating both rate limiting and the NETWORK signal.
    trusted_proxy_count: int = 0
    #: Defaults empty. No MFA enrolment or verification endpoint exists yet,
    #: so any role listed here cannot sign in at all - login would return
    #: MFA_REQUIRED with no way to satisfy it, locking those accounts out.
    #: Set this only once enrolment is built; the API refuses to boot
    #: otherwise (see `_assert_mfa_roles_are_enrollable` in `main.py`).
    mfa_required_roles: CsvList = Field(default_factory=list)

    @field_validator("jwt_private_key", "jwt_public_key")
    @classmethod
    def _decodable(cls, v: SecretStr) -> SecretStr:
        raw = v.get_secret_value()
        if raw.startswith("CHANGEME"):
            raise ValueError("JWT keys are still placeholders. Run scripts/generate-keys.sh")
        try:
            base64.b64decode(raw, validate=True)
        except Exception as exc:
            raise ValueError("JWT keys must be base64-encoded PEM") from exc
        return v

    @field_validator("otp_pepper", "token_pepper", "encryption_key")
    @classmethod
    def _strong_secret(cls, v: SecretStr) -> SecretStr:
        raw = v.get_secret_value()
        if raw.startswith("CHANGEME"):
            raise ValueError("Secret is still a placeholder. Run scripts/generate-keys.sh")
        if len(raw) < 32:
            raise ValueError("Secrets must be at least 32 bytes of entropy")
        return v

    def pem_private_key(self) -> bytes:
        return base64.b64decode(self.jwt_private_key.get_secret_value())

    def pem_public_key(self) -> bytes:
        return base64.b64decode(self.jwt_public_key.get_secret_value())

    def aes_key(self) -> bytes:
        return base64.b64decode(self.encryption_key.get_secret_value())


class AiSettings(_Base):
    #: The escape hatch that makes the whole system demonstrable offline
    #: (NFR-8): every AI port resolves to a deterministic fake.
    use_fake_ai: bool = True
    ai_provider: Literal["openai", "anthropic"] = "anthropic"
    ai_openai_api_key: SecretStr | None = None
    ai_openai_model: str = "gpt-4o-mini"
    ai_anthropic_api_key: SecretStr | None = None
    ai_anthropic_model: str = "claude-sonnet-4-5"
    ai_request_timeout_seconds: int = 30
    ai_max_retries: int = 3
    ai_max_output_tokens: int = 2048
    ai_monthly_budget_usd: float = 50.0
    ai_prompt_version: str = "v1"

    #: Which OCR implementation to build. `rapidocr` runs the same class of
    #: model through onnxruntime instead of PyTorch, which is what makes the
    #: worker image small enough for a free tier. Both stay selectable so
    #: Phase 1 can benchmark them against real CNICs (P1-01) and the report
    #: can quote a measured comparison rather than a preference.
    ocr_engine: Literal["easyocr", "rapidocr"] = "easyocr"
    ocr_languages: CsvList = Field(default_factory=lambda: ["en"])
    ocr_min_confidence: float = 0.60
    ocr_gpu: bool = False

    #: `insightface` drops TensorFlow for onnxruntime. DeepFace's default model
    #: is ArcFace, which is InsightFace's own, so this is the same family of
    #: model on a lighter runtime rather than a different approach.
    face_engine: Literal["deepface", "insightface"] = "deepface"
    face_match_model: str = "ArcFace"
    #: InsightFace's packaged model bundle. Small by default: on a CPU-only
    #: free tier the large model's cold start costs more than its accuracy
    #: gains, and a demo that times out scores nothing.
    face_onnx_model: str = "buffalo_s"
    face_detector_backend: str = "retinaface"
    face_match_threshold: float = 0.70
    #: Between the lower bound and the threshold, route to a human rather than
    #: auto-failing: face matching has demographic error-rate disparities and a
    #: false rejection costs a real person their ability to trade.
    face_match_review_lower: float = 0.55

    classifier_model_version: str = "scamclf-v1"
    #: `None` means "use the threshold the artifact was calibrated with".
    #:
    #: The operating point is chosen against a validation curve during training
    #: and stored in the artifact, so a hard default here would silently
    #: override a measured decision with a guessed one. Set it only to move the
    #: operating point deliberately, and record why.
    classifier_threshold: float | None = None

    @model_validator(mode="after")
    def _key_present_for_live_provider(self) -> AiSettings:
        if self.use_fake_ai:
            return self
        key = (
            self.ai_anthropic_api_key if self.ai_provider == "anthropic" else self.ai_openai_api_key
        )
        if key is None or not key.get_secret_value():
            raise ValueError(
                f"AI_PROVIDER={self.ai_provider} requires its API key, "
                "or set USE_FAKE_AI=true to run without one."
            )
        return self

    @model_validator(mode="after")
    def _thresholds_ordered(self) -> AiSettings:
        if self.face_match_review_lower >= self.face_match_threshold:
            raise ValueError(
                "FACE_MATCH_REVIEW_LOWER must be below FACE_MATCH_THRESHOLD, "
                "otherwise the manual-review band is empty."
            )
        return self


class StorageSettings(_Base):
    storage_provider: Literal["s3", "local"] = "s3"
    storage_endpoint_url: str | None = None
    storage_region: str = "us-east-1"
    storage_access_key_id: SecretStr | None = None
    storage_secret_access_key: SecretStr | None = None
    storage_bucket_documents: str = "trustlens-documents"
    storage_bucket_listings: str = "trustlens-listings"
    storage_bucket_models: str = "trustlens-models"
    storage_presign_ttl_seconds: int = 300
    storage_max_upload_bytes: int = 10 * 1024 * 1024
    storage_allowed_mime: CsvList = Field(
        default_factory=lambda: ["image/jpeg", "image/png", "image/webp"]
    )
    #: A listing video (LST-01) is the one upload purpose that isn't a
    #: still image - its own, larger cap rather than raising the shared one
    #: for every purpose (CNIC, selfie, appeal evidence) that doesn't need it.
    storage_max_video_upload_bytes: int = 50 * 1024 * 1024
    storage_allowed_video_mime: CsvList = Field(default_factory=lambda: ["video/mp4"])
    media_retention_days_identity: int = 90


class GoogleAuthSettings(_Base):
    """Google Sign-In (OAuth 2.0 authorization-code flow).

    Both fields default to None rather than raising at boot: not every
    deployment - or every developer's machine - has a Google Cloud project
    set up, and "sign in with Google" degrading to "not offered" is a far
    better failure than the whole API refusing to start over it.
    """

    model_config = SettingsConfigDict(env_prefix="google_", extra="ignore")

    client_id: str | None = None
    client_secret: SecretStr | None = None
    redirect_uri: str = "http://localhost:8000/api/v1/auth/google/callback"

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)


class NotificationSettings(_Base):
    email_provider: Literal["smtp", "resend", "console"] = "console"
    email_from: str = "no-reply@trustlens.dev"
    email_from_name: str = "TrustLens"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_tls: bool = False
    resend_api_key: SecretStr | None = None

    sms_provider: Literal["twilio", "console"] = "console"
    twilio_account_sid: str | None = None
    twilio_auth_token: SecretStr | None = None
    twilio_from_number: str | None = None

    otp_length: int = 6
    otp_ttl_seconds: int = 300
    otp_max_attempts: int = 5
    otp_send_limit_hour: int = 3
    otp_send_limit_day: int = 10


class ScoringSettings(_Base):
    score_validity_days: int = 30
    score_min_evidence_weight: float = 40.0
    score_recompute_debounce_seconds: int = 10


class RateLimitSettings(_Base):
    model_config = SettingsConfigDict(env_prefix="rate_limit_", extra="ignore")

    enabled: bool = True
    anon_per_minute: int = 60
    user_per_minute: int = 300
    #: Per-ACCOUNT soft limit, feeding LoginThrottlePolicy.
    login_per_15min: int = 5
    #: Per-IP login limit. A separate number, not a multiple of the one above,
    #: because it answers a different attack: one address trying one password
    #: against a thousand different email addresses. Every attempt there hits
    #: an account that does not exist, so no per-account counter ever moves.
    #:
    #: 30 in 15 minutes is generous for a real person - who fails twice, not
    #: thirty times - while still being low enough to make spraying pointless.
    #: Raise it if the product ends up behind a shared NAT with many users.
    login_ip_per_15min: int = 30
    #: SOC-01's anti-spam/flood guard on sending a message - generous for a
    #: real conversation (a burst of quick replies), low enough to blunt a
    #: scripted spam/flood attempt.
    message_send_per_minute: int = 20
    #: BLK-03's guard on the two anonymous endpoints that send a real email
    #: (resend-verification, forgot-password) - low, since a real person
    #: retries at most a couple of times an hour, not dozens.
    email_send_per_hour: int = 5
    public_api_free_per_minute: int = 60
    public_api_partner_per_minute: int = 600
    #: Public API fails CLOSED (protects cost and data); auth fails OPEN
    #: (a Redis blip must not lock everyone out).
    fail_mode: Literal["open", "closed"] = "closed"


class ObservabilitySettings(_Base):
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1
    otel_exporter_otlp_endpoint: str | None = None
    otel_service_name: str = "trustlens-api"
    metrics_enabled: bool = True
    metrics_auth_token: SecretStr | None = None


class WorkerSettings(_Base):
    worker_concurrency: int = 4
    #: Restart the process after N jobs - bounds memory growth in the ML
    #: libraries, which are not always tidy about releasing tensors.
    worker_max_jobs: int = 100
    job_default_timeout_seconds: int = 120
    job_identity_timeout_seconds: int = 300
    job_max_tries: int = 3


class IpIntelSettings(_Base):
    ip_intel_provider: Literal["ipqualityscore", "ipapi", "offline"] = "offline"
    ip_intel_api_key: SecretStr | None = None
    ip_intel_timeout_seconds: int = 5
    ip_intel_cache_ttl_seconds: int = 86_400
    disposable_email_list_url: str | None = None
    phone_lookup_provider: Literal["twilio_lookup", "none"] = "none"


class Settings(_Base):
    """The composed application configuration."""

    env: Environment = Environment.DEVELOPMENT
    debug: bool = False
    app_name: str = "TrustLens"
    app_version: str = "0.1.0"
    api_base_url: str = "http://localhost:8000"
    web_base_url: str = "http://localhost:3000"
    admin_base_url: str = "http://localhost:3001"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["console", "json"] = "json"

    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    google_auth: GoogleAuthSettings = Field(default_factory=GoogleAuthSettings)
    ai: AiSettings = Field(default_factory=AiSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    scoring: ScoringSettings = Field(default_factory=ScoringSettings)
    rate_limit: RateLimitSettings = Field(default_factory=RateLimitSettings)
    observability: ObservabilitySettings = Field(default_factory=ObservabilitySettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    ip_intel: IpIntelSettings = Field(default_factory=IpIntelSettings)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        return self.env is Environment.PRODUCTION

    @model_validator(mode="after")
    def _production_hardening(self) -> Settings:
        """Assertions that only apply once the app is actually exposed.

        These have caught more real incidents than any amount of review: a
        wildcard CORS origin or DEBUG=true shipped to production is a single
        typo away at all times.
        """
        if self.env is not Environment.PRODUCTION:
            return self

        problems: list[str] = []
        if self.debug:
            problems.append("DEBUG must be false in production")
        if "*" in self.security.cors_origins or not self.security.cors_origins:
            problems.append("SECURITY_CORS_ORIGINS must be an explicit allowlist in production")
        if not self.database.db_ssl_require:
            problems.append("DB_SSL_REQUIRE must be true in production")
        if self.ai.use_fake_ai:
            problems.append("USE_FAKE_AI must be false in production")
        if self.security.api_key_prefix != "tl_live":
            problems.append("SECURITY_API_KEY_PREFIX must be 'tl_live' in production")
        if self.log_format != "json":
            problems.append("LOG_FORMAT must be 'json' in production")
        if self.storage.storage_endpoint_url and "minio:" in self.storage.storage_endpoint_url:
            problems.append(
                "STORAGE_ENDPOINT_URL still points at the internal 'minio:9000' compose "
                "hostname - presigned upload/download URLs built from it are unreachable "
                "from a browser. Point it at a publicly-reachable address (the published "
                "MinIO port, or a managed S3-compatible provider like Cloudflare R2)."
            )

        if problems:
            raise ValueError("Production configuration is unsafe:\n  - " + "\n  - ".join(problems))
        return self

    @property
    def expose_docs(self) -> bool:
        """Swagger for the internal API is disabled once deployed."""
        return not self.env.is_deployed


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Build settings once. Any failure aborts startup with a readable message.

    Failing loudly here is the point: a half-configured app that boots and then
    misbehaves under load is far worse than one that refuses to start.
    """
    try:
        return Settings()
    except Exception as exc:
        print(f"\n!! Configuration error:\n{exc}\n", file=sys.stderr)
        print(
            "   Check your .env against .env.example, then run: python scripts/check-env.py\n",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


__all__ = [
    "AiSettings",
    "DatabaseSettings",
    "Environment",
    "GoogleAuthSettings",
    "IpIntelSettings",
    "NotificationSettings",
    "ObservabilitySettings",
    "RateLimitSettings",
    "RedisSettings",
    "ScoringSettings",
    "SecuritySettings",
    "Settings",
    "StorageSettings",
    "WorkerSettings",
    "get_settings",
]
