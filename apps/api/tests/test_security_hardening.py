"""Security regressions with synthetic accounts and intercepted external providers.

These exercise HTTP/authorization boundaries without contacting user data. Real SQL
reservation and single-use behavior have separate isolated database tests.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from trustlens.shared.config.settings import Settings, DatabaseSettings
from trustlens.shared.crypto import JwtService
from trustlens.shared.logging import redact_processor
from trustlens.shared.telemetry import _scrub
from trustlens.shared.notifications import build_sms_sender
from trustlens.core.domain.errors import RateLimitExceeded, TokenInvalid
from trustlens_api.api import deps
from trustlens_api.api.v1.routers import auth, verification
from trustlens_api.api.v1.schemas.verification import UploadIntentRequest
from trustlens_api.main import create_app


@pytest.fixture
def context():
    settings = Settings(_env_file=None)
    now = datetime.now(UTC)
    uid, sid = uuid4(), uuid4()
    signer = JwtService(settings.security)
    token, _ = signer.issue_access_token(
        user_id=uid,
        roles=["BUYER"],
        permissions=[],
        permission_version=0,
        session_id=sid,
        jti=uuid4(),
        now=now,
    )
    c = NS(
        settings=settings,
        clock=NS(now=lambda: now),
        jwt=signer,
        cache=NS(get=AsyncMock(return_value=None)),
        rate_limiter=NS(hit=AsyncMock(return_value=(True, 10, 0))),
        ids=NS(new=uuid4),
        queue=NS(describe=AsyncMock(return_value=None), status=AsyncMock(return_value="queued")),
        storage=NS(
            presign_upload=AsyncMock(
                return_value=NS(
                    url="https://objects.example/upload",
                    fields={},
                    expires_at=now + timedelta(minutes=5),
                )
            )
        ),
    )
    u = MagicMock()
    u.users.session_allowed = AsyncMock(return_value=True)
    u.refresh_tokens.family_is_active = AsyncMock(return_value=True)
    u.job_runs.get_by_key = AsyncMock(return_value=None)
    u.sellers.get = AsyncMock(return_value=NS(user_id=uid))
    u.listings.get = AsyncMock(return_value=NS(seller_id=uuid4()))
    u.files.add = AsyncMock()
    u.files.check_upload_budget = AsyncMock()
    u.commit = AsyncMock()
    app = create_app(settings)
    app.state.container = c

    async def fake_uow():
        yield u

    app.dependency_overrides[deps.get_uow] = fake_uow
    return NS(
        settings=settings,
        now=now,
        uid=uid,
        sid=sid,
        c=c,
        u=u,
        app=app,
        headers={"Authorization": "Bearer " + token},
        meta=deps.RequestMeta("192.0.2.1", "test", None, "synthetic"),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,payload",
    [
        ("identity.verify", {"seller_id": str(uuid4())}),
        ("scoring.recompute_trust_score", {"seller_id": str(uuid4())}),
        ("listings.analyse_listing", {"listing_id": str(uuid4())}),
    ],
)
async def test_job_owner_can_poll_but_other_account_cannot(context, name, payload):
    x = context
    x.u.job_runs.get_by_key.return_value = NS(
        job_name=name,
        payload=payload,
        status="SUCCEEDED",
        result={
            "decision": "VERIFIED",
            "score": 80,
            "risk_level": "LOW",
            "risk_score": 10,
            "private": "PRIVATE_MARKER",
        },
        error_message=None,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=x.app), base_url="http://testserver"
    ) as client:
        res = await client.get("/api/v1/jobs/synthetic", headers=x.headers)
        assert res.status_code == 200, res.text
        assert "PRIVATE_MARKER" not in res.text
        x.u.sellers.get.return_value = NS(user_id=uuid4())
        res = await client.get("/api/v1/jobs/synthetic", headers=x.headers)
        assert res.status_code == 404, res.text


@pytest.mark.asyncio
async def test_queue_metadata_has_same_ownership_gate_and_errors_are_generic(context):
    x = context
    x.c.queue.describe.return_value = {
        "job_name": "identity.verify",
        "payload": {"seller_id": str(uuid4())},
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=x.app), base_url="http://testserver"
    ) as client:
        assert (await client.get("/api/v1/jobs/queued", headers=x.headers)).status_code == 200
        x.u.sellers.get.return_value = NS(user_id=uuid4())
        assert (await client.get("/api/v1/jobs/queued", headers=x.headers)).status_code == 404
        x.u.sellers.get.return_value = NS(user_id=x.uid)
        x.u.job_runs.get_by_key.return_value = NS(
            job_name="identity.verify",
            payload={"seller_id": str(uuid4())},
            status="FAILED",
            result=None,
            error_message="PRIVATE_STACK_AND_SQL",
        )
        res = await client.get("/api/v1/jobs/failed", headers=x.headers)
        assert res.status_code == 200 and "PRIVATE_STACK_AND_SQL" not in res.text
        assert "contact support" in res.json()["data"]["error"]


@pytest.mark.asyncio
async def test_revoked_session_denies_next_request_and_active_rotation_keeps_access(context):
    x = context
    req = NS(headers={k.lower(): v for k, v in x.headers.items()})
    assert (await deps.get_optional_actor(req, x.c, x.u)).session_id == x.sid
    x.u.refresh_tokens.family_is_active.return_value = False
    with pytest.raises(TokenInvalid):
        await deps.get_optional_actor(req, x.c, x.u)
    x.u.refresh_tokens.family_is_active.return_value = True
    assert (await deps.get_optional_actor(req, x.c, x.u)).user_id == x.uid


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["login", "email", "otp", "message"])
async def test_sensitive_limiters_fail_closed(context, kind):
    from trustlens_api.api.v1.routers.messaging import _throttle_send

    x = context
    x.c.rate_limiter.hit.side_effect = ConnectionError("PRIVATE_REDIS_PASSWORD")
    action = {
        "login": lambda: auth._throttle_login_by_ip(x.c, x.meta),
        "email": lambda: auth._throttle_email_send(x.c, x.meta, "reset"),
        "otp": lambda: verification._throttle_otp_request(x.c, x.meta),
        "message": lambda: _throttle_send(x.c, NS(user_id=x.uid)),
    }[kind]
    with pytest.raises(HTTPException) as error:
        await action()
    assert error.value.status_code == 503
    assert "PRIVATE" not in error.value.detail


@pytest.mark.asyncio
async def test_global_request_budget_has_retry_and_cache_failure_response(context):
    x = context
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=x.app), base_url="http://testserver"
    ) as client:
        x.c.rate_limiter.hit.return_value = (False, 0, 27)
        res = await client.get("/api/v1/public/listings")
        assert res.status_code == 429 and res.headers["retry-after"] == "27"
        assert "content-security-policy" in res.headers
        x.c.rate_limiter.hit.side_effect = ConnectionError("PRIVATE")
        res = await client.get("/api/v1/public/listings")
        assert res.status_code == 503 and "PRIVATE" not in res.text


@pytest.mark.asyncio
async def test_register_stops_before_hashing_when_budget_exhausted(context):
    x = context
    x.c.rate_limiter.hit.return_value = (False, 0, 60)
    body = auth.RegisterRequest(
        email="test@example.com",
        password="Synthetic!Password!1234",
        fullName="Test",
        acceptedTerms=True,
    )
    with patch.object(auth, "RegisterUser") as use_case:
        with pytest.raises(RateLimitExceeded):
            await auth.register(body, x.c, x.u, x.meta, NS())
        use_case.assert_not_called()


@pytest.mark.asyncio
async def test_upload_reserves_quota_and_signs_only_declared_bytes(context):
    x = context
    body = UploadIntentRequest(
        filename="test.jpg", contentType="image/jpeg", sizeBytes=1000, purpose="LISTING_IMAGE"
    )
    result = await verification.upload_intent(body, NS(user_id=x.uid), x.c, x.u, x.meta)
    assert result["data"]["maxBytes"] == 1000
    assert x.c.storage.presign_upload.call_args.kwargs["max_bytes"] == 1000
    assert x.u.files.check_upload_budget.call_args.kwargs["requested_bytes"] == 1000
    x.u.files.check_upload_budget.side_effect = RateLimitExceeded(
        "Quota exceeded", retry_after=3600
    )
    x.c.storage.presign_upload.reset_mock()
    with pytest.raises(RateLimitExceeded):
        await verification.upload_intent(body, NS(user_id=x.uid), x.c, x.u, x.meta)
    x.c.storage.presign_upload.assert_not_awaited()


@pytest.mark.parametrize(
    "query",
    ["sslmode=disable", "sslmode=prefer", "sslmode=require&sslmode=disable", "sslmode=allow", ""],
)
def test_migration_tls_cannot_be_downgraded(context, query):
    config = context.settings.database.model_dump()
    config.update(
        db_ssl_require=True,
        database_url_sync="postgresql+psycopg://test:test@localhost/test?" + query,
    )
    with pytest.raises(ValidationError):
        DatabaseSettings.model_validate(config)


@pytest.mark.parametrize("query", ["sslmode=require", "sslmode=verify-ca", "sslmode=verify-full"])
def test_explicit_database_tls_is_accepted(context, query):
    config = context.settings.database.model_dump()
    config.update(
        db_ssl_require=True,
        database_url_sync="postgresql+psycopg://test:test@localhost/test?" + query,
    )
    assert DatabaseSettings.model_validate(config).db_ssl_require


@pytest.mark.parametrize("provider", ["console", "mailpit"])
def test_production_refuses_local_sms_transports(context, provider):
    config = context.settings.model_dump()
    config["env"] = "production"
    config["notifications"]["sms_provider"] = provider
    with pytest.raises(ValidationError) as err:
        Settings.model_validate(config)
    assert "Production SMS" in str(err.value)


@pytest.mark.parametrize("provider", ["console", "resend"])
def test_production_refuses_console_email_or_missing_provider_key(context, provider):
    config = context.settings.model_dump()
    config["env"] = "production"
    config["notifications"].update(email_provider=provider, resend_api_key=None)
    with pytest.raises(ValidationError) as err:
        Settings.model_validate(config)
    assert ("Production email" if provider == "console" else "RESEND_API_KEY") in str(err.value)


@pytest.mark.asyncio
async def test_local_otp_goes_to_mailpit_not_console(context, capsys):
    from trustlens.shared.notifications import SmtpEmailSender

    config = context.settings.notifications.model_copy(
        update={"sms_provider": "mailpit", "email_provider": "smtp"}
    )
    with patch.object(SmtpEmailSender, "send", new_callable=AsyncMock) as send:
        await build_sms_sender(config).send(to="+12025550123", message="PRIVATE_OTP_123456")
        assert send.await_count == 1
        assert send.call_args.kwargs["to"] == "sms@localhost.test"
        assert "PRIVATE_OTP_123456" in str(send.call_args.kwargs["context"])
    assert "PRIVATE_OTP_123456" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "value",
    [
        {"payload": {"name": "PRIVATE_MARKER"}},
        {"query": "token=PRIVATE_MARKER"},
        {"exception": "PRIVATE_MARKER"},
        {"headers": {"Authorization": "PRIVATE_MARKER"}},
        {"unknown": {"a": {"b": {"c": {"d": {"e": {"f": {"g": "PRIVATE_MARKER"}}}}}}}},
        {"error": "PRIVATE_MARKER"},
        {"message": "token=PRIVATE_MARKER"},
    ],
)
def test_structured_logs_remove_sensitive_data(value):
    assert "PRIVATE_MARKER" not in str(redact_processor(None, "info", value))


@pytest.mark.parametrize(
    "exception",
    [
        None,
        "PRIVATE_MARKER",
        {"value": "PRIVATE_MARKER"},
        {
            "values": [
                {
                    "type": "ValueError",
                    "value": "PRIVATE_MARKER",
                    "stacktrace": {
                        "frames": [
                            {
                                "filename": "/home/PRIVATE_MARKER/app.py",
                                "function": "run",
                                "vars": {"token": "PRIVATE_MARKER"},
                                "lineno": 3,
                            }
                        ]
                    },
                }
            ]
        },
    ],
)
def test_sentry_only_exports_projected_locations(exception):
    result = _scrub(
        {
            "exception": exception,
            "request": {"body": "PRIVATE_MARKER"},
            "user": {"email": "PRIVATE_MARKER"},
            "breadcrumbs": [{"message": "PRIVATE_MARKER"}],
        },
        {},
    )
    assert "PRIVATE_MARKER" not in str(result)
    assert set(result) <= {"exception"}


@pytest.mark.asyncio
async def test_health_does_not_publish_internal_configuration(context):
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=context.app), base_url="http://testserver"
    ) as client:
        response = await client.get("/health/live")
        assert response.status_code == 200 and set(response.json()) == {"status"}


@pytest.mark.asyncio
async def test_disabled_sms_refuses_request_without_queueing(context):
    from trustlens.core.domain.errors import InvalidStateError

    x = context
    x.settings.notifications.sms_provider = "disabled"
    with patch.object(verification, "RequestPhoneOtp") as use_case:
        with pytest.raises(InvalidStateError):
            await verification.request_otp(
                NS(phone_number="+12025550123"), NS(user_id=x.uid), x.c, x.u, x.meta
            )
        use_case.assert_not_called()
