"""Pre-deployment security probes. Uses synthetic credentials and isolated ASGI apps.
Run: python run_checks.py --root /path/to/TrustLens --out /path/to/evidence
No user database, remote APIs or deployment are modified. Session repository state is synthetic; database tests cover SQL behavior separately.
"""

import argparse, asyncio, base64, csv, importlib.util, json, os, re, sys
from pathlib import Path
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

args = argparse.ArgumentParser()
args.add_argument("--root", type=Path, required=True)
args.add_argument("--out", type=Path, required=True)
opt = args.parse_args()
root = opt.root.resolve()
out = opt.out.resolve()
out.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location("testenv", root / "testing/python/run_unit_tests.py")
envmod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(envmod)
os.environ.update(envmod.environment(root))
sys.path[:0] = os.environ["PYTHONPATH"].split(os.pathsep)
for name in ("ALL_PROXY", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(name, None)
import httpx, jwt
from fastapi import FastAPI, Request, Response
from fastapi.routing import iter_route_contexts
from trustlens.shared.config.settings import Settings, Environment
from trustlens.shared.crypto import JwtService, Argon2PasswordHasher, PepperedTokenHasher
from trustlens.shared.logging import redact_processor
from trustlens.shared.telemetry import _scrub
from trustlens_api.middleware import install_middleware, BodySizeLimitMiddleware
from trustlens_api.exceptions.handlers import register_exception_handlers
from trustlens_api.main import create_app, _PUBLIC_ROUTES, _assert_routes_are_guarded
from trustlens_api.api import deps
from trustlens_api.api.v1.routers import auth
from trustlens_api.core.cookies import set_refresh_cookie
from trustlens.core.domain.entities import User
from trustlens.core.domain.enums import UserRole, AccountStatus
from trustlens.core.domain.value_objects import Email
from trustlens.core.domain.errors import TokenInvalid

settings = Settings(_env_file=None)
now = datetime.now(UTC)
uid = uuid4()
sid = uuid4()
signer = JwtService(settings.security)
results = []


def record(id, ok, observed):
    results.append({"id": id, "status": "PASS" if ok else "FAIL", "observed": observed})


def issue(**changes):
    token, _ = signer.issue_access_token(
        user_id=uid,
        roles=["BUYER"],
        permissions=[],
        permission_version=0,
        session_id=sid,
        jti=uuid4(),
        now=now,
    )
    if changes:
        claims = jwt.decode(token, options={"verify_signature": False})
        claims.update(changes)
        return jwt.encode(claims, settings.security.pem_private_key(), algorithm="EdDSA")
    return token


def deps_names(d):
    return [getattr(d.call, "__name__", "")] + [
        n for child in d.dependencies for n in deps_names(child)
    ]


async def main():
    # Real crypto, no mocked signature verification.
    good = issue()
    record(
        "JWT-valid", signer.decode(good)["sub"] == str(uid), "Ed25519 signed access token accepted"
    )
    variants = {
        "expired": issue(exp=int((now - timedelta(seconds=60)).timestamp())),
        "issuer": issue(iss="https://attacker.invalid"),
        "audience": issue(aud="other"),
        "malformed": "not.a.jwt",
        "none": jwt.encode(
            {"sub": str(uid), "exp": int(now.timestamp()) + 99}, key="", algorithm="none"
        ),
    }
    parts = good.split(".")
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==="))
    payload["roles"] = ["ADMIN"]
    parts[1] = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    variants["role-tamper"] = ".".join(parts)
    for name, token in variants.items():
        try:
            signer.decode(token)
            ok = False
        except jwt.PyJWTError:
            ok = True
        record("JWT-" + name, ok, "rejected" if ok else "accepted")
    claims = jwt.decode(good, options={"verify_signature": False})
    for missing in ("exp", "iat", "sub", "jti", "iss", "aud"):
        changed = dict(claims)
        changed.pop(missing, None)
        token = jwt.encode(changed, settings.security.pem_private_key(), algorithm="EdDSA")
        try:
            signer.decode(token)
            ok = False
        except jwt.PyJWTError:
            ok = True
        record(
            "JWT-required-" + missing,
            ok,
            "missing claim rejected" if ok else "missing claim accepted",
        )
    hasher = Argon2PasswordHasher(settings.security)
    ph = hasher.hash("Synthetic!Strong!314159")
    record(
        "password-hashing",
        ph.startswith("$argon2id$")
        and hasher.verify("Synthetic!Strong!314159", ph)
        and not hasher.verify("wrong", ph),
        "Argon2id, correct password accepted / wrong rejected",
    )
    token_hasher = PepperedTokenHasher(settings.security.token_pepper.get_secret_value().encode())
    # Actual auth dependencies and logout route, in-memory repository boundary.
    uow = MagicMock()
    uow.api_clients.get_key_by_prefix = AsyncMock(return_value=None)
    uow.users.session_allowed = AsyncMock(return_value=True)
    uow.refresh_tokens.get_by_hash = AsyncMock(return_value=NS(id=uuid4(), family_id=sid))
    uow.refresh_tokens.revoke_family = AsyncMock(return_value=1)
    uow.refresh_tokens.revoke_all_for_user = AsyncMock(return_value=1)
    uow.commit = AsyncMock()
    container = NS(
        settings=settings,
        rate_limiter=NS(hit=AsyncMock(return_value=(True, 10, 0))),
        jwt=signer,
        cache=NS(get=AsyncMock(return_value=None)),
        clock=NS(now=lambda: now),
        token_hasher=token_hasher,
    )
    active = {"value": True}

    async def revoke(*args, **kwargs):
        active["value"] = False
        return 1

    uow.refresh_tokens.family_is_active = AsyncMock(
        side_effect=lambda *args, **kwargs: active["value"]
    )
    uow.refresh_tokens.revoke_family.side_effect = revoke
    uow.refresh_tokens.revoke_all_for_user.side_effect = revoke
    req = NS(headers={"authorization": "Bearer " + good})
    meta = deps.RequestMeta("192.0.2.4", "security-audit", None, "audit-request")
    before = await deps.get_optional_actor(req, container, uow)
    await auth.logout(Response(), container, uow, meta, "synthetic-refresh")
    try:
        await deps.get_optional_actor(req, container, uow)
        rejected = False
    except TokenInvalid:
        rejected = True
    record(
        "logout-access-revocation",
        rejected,
        {
            "refresh_family_revoked": uow.refresh_tokens.revoke_family.await_count == 1,
            "old_access_token_rejected": rejected,
            "token_ttl_minutes": settings.security.access_token_ttl_minutes,
        },
    )
    await auth.logout_all(Response(), before, container, uow, meta)
    try:
        await deps.get_optional_actor(req, container, uow)
        rejected = False
    except TokenInvalid:
        rejected = True
    record(
        "logout-all-access-revocation",
        rejected,
        "old bearer " + ("rejected" if rejected else "accepted") + " after logout-all",
    )
    active["value"] = True
    uow.users.session_allowed.return_value = False
    try:
        await deps.get_optional_actor(req, container, uow)
        ok = False
    except TokenInvalid:
        ok = True
    record("inactive-account-access", ok, "inactive account rejected")
    uow.users.session_allowed.return_value = True
    container.cache.get.return_value = "1"
    try:
        await deps.get_optional_actor(req, container, uow)
        ok = False
    except TokenInvalid:
        ok = True
    record("permission-version-revocation", ok, "changed permission version rejected")
    container.cache.get.return_value = None
    # Reset token creation invokes real endpoint, fake outbound queue/repository.
    user = User(
        id=uid,
        email=Email("audit@example.com"),
        full_name="Synthetic User",
        status=AccountStatus.ACTIVE,
        primary_role=UserRole.BUYER,
        created_at=now,
    )
    uow.users.get_by_email = AsyncMock(return_value=user)
    uow.verification_tokens.invalidate_for_user = AsyncMock()
    uow.verification_tokens.add = AsyncMock()
    container.ids = NS(new=uuid4)
    container.queue = NS(enqueue=AsyncMock())
    container.rate_limiter = NS(hit=AsyncMock(return_value=(True, 10, 0)))
    await auth.forgot_password(
        auth.ForgotPasswordRequest(email=user.email.value), container, uow, meta
    )
    made = uow.verification_tokens.add.call_args.args[0]
    ttl = (made.expires_at - made.created_at).total_seconds()
    record(
        "reset-maximum-15-minutes",
        ttl <= 900,
        {
            "ttl_seconds": ttl,
            "bound_to_user": made.user_id == uid,
            "stored_hash_only": isinstance(made.token_hash, bytes),
        },
    )
    # Actual throttle helper budgets plus fail behavior.
    await auth._throttle_login_by_ip(container, meta)
    call = container.rate_limiter.hit.call_args_list[-2]
    record(
        "login-5-per-minute",
        call.kwargs["limit"] <= 5 and call.kwargs["window_seconds"] <= 60,
        dict(call.kwargs),
    )
    await auth._throttle_email_send(container, meta, "forgot-password:ip")
    call = container.rate_limiter.hit.call_args
    record("reset-3-per-hour", call.kwargs["limit"] <= 3, dict(call.kwargs))
    container.rate_limiter.hit.side_effect = ConnectionError("synthetic cache outage")
    try:
        await auth._throttle_login_by_ip(container, meta)
        closed = False
    except Exception:
        closed = True
    record(
        "auth-rate-outage-protection",
        closed,
        "limiter outage " + ("blocks" if closed else "allows") + " login attempts",
    )
    # Cookie security in production settings without any deployed requests.
    deployed = settings.model_copy(update={"env": Environment.PRODUCTION})
    response = Response()
    set_refresh_cookie(
        response, deployed, token="synthetic-refresh", expires_at=now + timedelta(days=1)
    )
    cookie = response.headers["set-cookie"].lower()
    record(
        "refresh-cookie-flags",
        all(x in cookie for x in ["httponly", "secure", "samesite=lax"]),
        {
            "httpOnly": "httponly" in cookie,
            "secure": "secure" in cookie,
            "sameSiteLax": "samesite=lax" in cookie,
        },
    )
    # Local HTTP boundary: no DB/server/network dependency required.
    app = FastAPI()
    app.state.settings = deployed
    register_exception_handlers(app)
    install_middleware(app, deployed)

    @app.get("/ok")
    async def ok():
        return {"ok": True}

    @app.get("/boom")
    async def boom():
        raise RuntimeError("SYNTHETIC_PRIVATE_MARKER /private/source.py SELECT secret FROM users")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        normal = await client.get("/ok")
        bad = await client.get("/boom")
        expected = [
            "x-content-type-options",
            "x-frame-options",
            "strict-transport-security",
            "content-security-policy",
            "x-request-id",
        ]
        record(
            "api-normal-security-headers",
            all(k in normal.headers for k in expected),
            {k: normal.headers.get(k) for k in expected},
        )
        record(
            "api-unhandled-error-headers",
            all(k in bad.headers for k in expected),
            {k: bad.headers.get(k) for k in expected},
        )
        record(
            "api-generic-500",
            bad.status_code == 500 and "SYNTHETIC_PRIVATE_MARKER" not in bad.text,
            {"status": bad.status_code, "body": bad.json()},
        )
        r = await client.options(
            "/ok",
            headers={"Origin": "https://evil.invalid", "Access-Control-Request-Method": "GET"},
        )
        record(
            "cors-untrusted-origin",
            r.status_code == 400 and "access-control-allow-origin" not in r.headers,
            {"status": r.status_code},
        )
        with patch("trustlens_api.middleware.log") as log:
            await client.get("/ok?code=SYNTHETIC_OAUTH_CODE&email=person%40example.test")
        query = log.info.call_args.kwargs.get("query")
        clean = redact_processor(None, "info", {"query": query})
        record("access-log-query-redaction", "SYNTHETIC_OAUTH_CODE" not in json.dumps(clean), clean)
    bodyapp = FastAPI()
    bodyapp.add_middleware(BodySizeLimitMiddleware, max_bytes=64)

    @bodyapp.post("/read")
    async def read(request: Request):
        return {"received_bytes": len(await request.body())}

    async def chunks():
        yield b"x" * 65

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=bodyapp), base_url="http://testserver"
    ) as c:
        r = await c.post("/read", content=b"x" * 65)
        record("body-declared-limit", r.status_code == 413, {"status": r.status_code})
        r = await c.post("/read", content=chunks())
        record(
            "body-streamed-limit",
            r.status_code == 413,
            {"status": r.status_code, "response": r.json()},
        )
    nested = {"password": "SYNTHETIC_PRIVATE_MARKER"}
    for _ in range(8):
        nested = {"level": nested}
    record(
        "log-deep-redaction",
        "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(redact_processor(None, "info", nested)),
        "8-level synthetic password "
        + (
            "redacted"
            if "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(redact_processor(None, "info", nested))
            else "retained"
        ),
    )
    sentry = _scrub(
        {
            "user": {"email": "audit@example.test"},
            "request": {"query_string": "token=SYNTHETIC_PRIVATE_MARKER"},
            "exception": {"value": "password=SYNTHETIC_PRIVATE_MARKER"},
        },
        {},
    )
    record(
        "sentry-pii-scrub",
        "SYNTHETIC_PRIVATE_MARKER" not in json.dumps(sentry)
        and "audit@example.test" not in json.dumps(sentry),
        sentry,
    )
    # Full route inventory and anonymous / malformed bearer probes.
    container.rate_limiter.hit.side_effect = None
    container.rate_limiter.hit.return_value = (True, 10, 0)
    full = create_app(settings)
    full.state.container = container

    async def fake_uow():
        yield uow

    full.dependency_overrides[deps.get_uow] = fake_uow
    _assert_routes_are_guarded(full)
    inventory = []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=full, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as c:
        for ctx in iter_route_contexts(full.routes):
            dep = getattr(ctx, "dependant", None)
            path = getattr(ctx, "path", "")
            if dep is None or not path:
                continue
            names = deps_names(dep)
            for method in sorted(ctx.methods or []):
                row = {
                    "path": path,
                    "method": method,
                    "public": path in _PUBLIC_ROUTES,
                    "dependencies": ",".join(sorted(set(names))),
                }
                if not row["public"]:
                    url = re.sub(r"\{[^}]+\}", str(uuid4()), path)
                    for mode, headers in [
                        ("anonymous", {}),
                        ("malformed", {"Authorization": "Bearer not.a.jwt"}),
                    ]:
                        res = await c.request(
                            method,
                            url,
                            headers=headers,
                            json={} if method not in ("GET", "HEAD", "DELETE") else None,
                        )
                        row[mode] = res.status_code
                    if path.startswith("/api/v1/admin") or path.startswith("/api/v1/moderation"):
                        res = await c.request(
                            method,
                            url,
                            headers={"Authorization": "Bearer " + good},
                            json={} if method not in ("GET", "HEAD", "DELETE") else None,
                        )
                        row["buyer"] = res.status_code
                inventory.append(row)
    fields = ["path", "method", "public", "dependencies", "anonymous", "malformed", "buyer"]
    with (out / "route-access.csv").open("w") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(inventory)
    protected = [x for x in inventory if not x["public"]]
    for mode in ["anonymous", "malformed"]:
        gaps = [
            {k: x.get(k) for k in ("path", "method", mode)}
            for x in protected
            if x.get(mode) not in (401, 403)
        ]
        record(
            "routes-" + mode + "-blocked",
            not gaps,
            {"protected_operations": len(protected), "unexpected": gaps},
        )
    admin = [x for x in protected if "buyer" in x]
    gaps = [{k: x[k] for k in ("path", "method", "buyer")} for x in admin if x["buyer"] != 403]
    record("admin-buyer-blocked", not gaps, {"operations": len(admin), "unexpected": gaps})
    (out / "security-results.json").write_text(json.dumps(results, indent=2))
    print(
        json.dumps(
            {
                "checks": len(results),
                "pass": sum(x["status"] == "PASS" for x in results),
                "fail": [x["id"] for x in results if x["status"] == "FAIL"],
                "route_operations": len(inventory),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
