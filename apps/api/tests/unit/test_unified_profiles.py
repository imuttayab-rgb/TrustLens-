"""Profile invariants. Synthetic inputs only; no real faces, IDs or accounts."""

from dataclasses import replace
from datetime import UTC, datetime
from io import BytesIO
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import create_engine, select

from trustlens.core.domain.errors import ConflictError, EntityNotFound, ValidationError
from trustlens.core.domain.policies.profile import (
    can_confirm_name,
    clean_name,
    photo_result_approved,
    public_name,
)
from trustlens.core.domain.ports.ai import FaceMatchResult
from trustlens.db import models as m
from trustlens.db.profiles import profile_ready
from trustlens_api.api.v1.routers import messaging, profiles
from trustlens_api.modules.profiles.service import prepare_avatar


def result(value=None):
    r = Mock()
    r.scalar_one_or_none.return_value = value
    r.scalar_one.return_value = value
    r.first.return_value = None
    return r


@pytest.mark.parametrize(
    "engine,confidence,entered,expected",
    [
        ("rapidocr", 0.95, "  Ahmed   ALI  ", True),
        ("fake", 1, "Ahmed Ali", False),
        ("mock", 1, "Ahmed Ali", False),
        ("rapidocr", 0.84, "Ahmed Ali", False),
        ("rapidocr", 0.99, "Ahmad Ali", False),
        ("rapidocr", float("nan"), "Ahmed Ali", False),
        ("rapidocr", 2, "Ahmed Ali", False),
    ],
)
def test_name_match_is_exact_and_real(engine, confidence, entered, expected):
    assert can_confirm_name(entered, "Ahmed Ali", engine=engine, confidence=confidence) is expected


def test_public_name_and_unicode():
    assert public_name("Ahmed Hassan Ali") == "Ahmed Ali"
    assert clean_name("مُحمد علی") == "مُحمد علی"
    for bad in ["a", "--", "John 123", "John\x00 Doe"]:
        with pytest.raises(ValueError):
            clean_name(bad)


GOOD = FaceMatchResult(
    0.93,
    0.07,
    0.80,
    "insightface",
    "test",
    raw={"profile_face_count": 1, "reference_face_count": 1},
)


@pytest.mark.parametrize(
    "changes",
    [
        {"engine": "fake"},
        {"similarity": 0.79},
        {"threshold": 0.1},
        {"similarity": float("nan")},
        {"face_detected_in_selfie": False},
        {"raw": {"profile_face_count": 2, "reference_face_count": 1}},
        {"raw": {"profile_face_count": 1, "reference_face_count": 0}},
        {"raw": {}},
    ],
)
def test_photo_rejects_unreliable_evidence(changes):
    assert photo_result_approved(GOOD)
    assert not photo_result_approved(replace(GOOD, **changes))


def test_photo_normalizes_strips_metadata_and_rejects_bad_input():
    img = Image.new("RGB", (1200, 900))
    exif = Image.Exif()
    exif[270] = "private caption"
    buf = BytesIO()
    img.save(buf, "JPEG", exif=exif)
    output = prepare_avatar(buf.getvalue())
    with Image.open(BytesIO(output)) as normalized:
        assert max(normalized.size) <= 800
        assert not normalized.getexif()
    with pytest.raises(ValueError):
        prepare_avatar(b"x" * (5 * 1024 * 1024 + 1))
    buf = BytesIO()
    Image.new("RGB", (80, 80)).save(buf, "PNG")
    with pytest.raises(ValueError):
        prepare_avatar(buf.getvalue())


@pytest.mark.asyncio
async def test_username_is_chosen_once_and_other_fields_remain_editable(monkeypatch):
    uid = uuid4()
    seller = NS(id=uuid4(), handle="suggested-name", user_id=uid, city=None, bio=None)
    p = NS(username_locked=False, version=1)
    user = NS(id=uid)
    monkeypatch.setattr(profiles, "owner", AsyncMock(return_value=user))
    monkeypatch.setattr(profiles, "profile_payload", AsyncMock(return_value={}))
    session = NS(
        execute=AsyncMock(),
        get=AsyncMock(
            side_effect=lambda model, pk, **kwargs: p if model is m.AccountProfileModel else None
        ),
    )
    uow = NS(session=session, commit=AsyncMock())
    container = NS(clock=NS(now=lambda: datetime.now(UTC)), cache=NS(delete=AsyncMock()))
    actor = NS(user_id=uid)
    meta = NS(request_id="test")
    session.execute.side_effect = [result(), result(seller)]
    with pytest.raises(ValidationError):
        await profiles.edit_profile(
            profiles.ProfileEdit(handle="my-first-name", version=1), actor, container, uow, meta
        )
    assert not p.username_locked and seller.handle == "suggested-name"
    session.execute.side_effect = [result(), result(seller), result(None), result(), result()]
    await profiles.edit_profile(
        profiles.ProfileEdit(handle="my-first-name", version=1, confirm_username=True),
        actor,
        container,
        uow,
        meta,
    )
    assert p.username_locked and seller.handle == "my-first-name"
    session.execute.side_effect = [result(), result(seller)]
    with pytest.raises(ValidationError):
        await profiles.edit_profile(
            profiles.ProfileEdit(handle="changed-name", version=2, confirm_username=True),
            actor,
            container,
            uow,
            meta,
        )
    assert seller.handle == "my-first-name"
    session.execute.side_effect = [result(), result(seller), result(uid), result()]
    await profiles.edit_profile(
        profiles.ProfileEdit(handle="my-first-name", version=2, city="Lahore", bio="Hello"),
        actor,
        container,
        uow,
        meta,
    )
    assert seller.city == "Lahore" and seller.bio == "Hello" and p.username_locked


@pytest.mark.asyncio
async def test_stale_profile_version_is_rejected(monkeypatch):
    uid = uuid4()
    monkeypatch.setattr(profiles, "owner", AsyncMock(return_value=NS(id=uid)))
    session = NS(
        get=AsyncMock(return_value=NS(version=3)),
        execute=AsyncMock(side_effect=[result(), result(NS(handle="old"))]),
    )
    with pytest.raises(ConflictError):
        await profiles.edit_profile(
            profiles.ProfileEdit(handle="new", version=1, confirm_username=True),
            NS(user_id=uid),
            None,
            NS(session=session),
            NS(request_id="t"),
        )


@pytest.mark.asyncio
async def test_chat_header_denies_third_party():
    uow = NS(messaging=NS(get_participants=AsyncMock(return_value=(uuid4(), uuid4()))))
    with pytest.raises(EntityNotFound):
        await messaging.get_conversation(uuid4(), NS(user_id=uuid4()), uow, NS(request_id="t"), NS(clock=NS(now=lambda: datetime.now(UTC))))


@pytest.mark.asyncio
@pytest.mark.parametrize("seller_side", [False, True])
async def test_chat_profile_links_use_the_other_user_id(seller_side):
    buyer, seller_user = uuid4(), uuid4()
    now = datetime.now(UTC)
    cid = uuid4()
    c = NS(
        id=cid,
        listing_id=None,
        listing_title="Phone",
        last_message_at=now,
        created_at=now,
        muted_by_buyer=False,
        muted_by_seller=False,
    )
    flags = Mock()
    flags.one.return_value = (True, True)
    p = NS(public_name="Ahmed Ali", approved_photo_id=uuid4())
    uow = NS(
        messaging=NS(
            get_participants=AsyncMock(return_value=(buyer, seller_user)),
            get_conversation=AsyncMock(return_value=c),
        ),
        session=NS(
            get=AsyncMock(return_value=p), execute=AsyncMock(side_effect=[flags, result(None)])
        ),
    )
    uow.blocks = NS(is_blocked_either_way=AsyncMock(return_value=False))
    current = seller_user if seller_side else buyer
    other = buyer if seller_side else seller_user
    response = await messaging.get_conversation(cid, NS(user_id=current), uow, NS(request_id="t"), NS(clock=NS(now=lambda: datetime.now(UTC))))
    assert response["data"]["counterpartProfileUrl"] == f"/profile/{other}"
    assert response["data"]["counterpartUserId"] == str(other)
    assert "fullName" not in response["data"]


@pytest.fixture
def eligibility_db():
    """Execute actual correlated eligibility SQL with minimal synthetic SQLite tables.
    PostgreSQL migrations/types are separately checked by the local installer.
    """
    engine = create_engine("sqlite://")
    conn = engine.connect()
    schema = {
        "users": "id TEXT, deleted_at TEXT, status TEXT",
        "seller_profiles": "id TEXT,user_id TEXT,identity_status TEXT,deleted_at TEXT,is_flagged BOOLEAN",
        "identity_documents": "id TEXT,seller_id TEXT,document_type TEXT,deleted_at TEXT,extracted_expiry DATE",
        "identity_verifications": "id TEXT,seller_id TEXT,created_at TEXT,decision TEXT,decision_reason TEXT,front_document_id TEXT,selfie_document_id TEXT,face_match_engine TEXT",
        "account_profiles": "user_id TEXT,username_locked BOOLEAN,name_status TEXT,name_verified_at TEXT,public_name TEXT,name_identity_id TEXT,approved_photo_id TEXT",
        "profile_photos": "id TEXT,user_id TEXT,status TEXT,deleted_at TEXT,identity_id TEXT,engine TEXT,threshold NUMERIC,similarity NUMERIC",
    }
    for table, columns in schema.items():
        conn.exec_driver_sql(f"CREATE TABLE {table} ({columns})")
    ids = {k: uuid4().hex for k in ("user", "seller", "front", "selfie", "identity", "photo")}
    conn.exec_driver_sql("INSERT INTO users VALUES (?,NULL,?)", (ids["user"], "ACTIVE"))
    conn.exec_driver_sql(
        "INSERT INTO seller_profiles VALUES (?,?,?,NULL,0)",
        (ids["seller"], ids["user"], "VERIFIED"),
    )
    for k, t in [("front", "CNIC_FRONT"), ("selfie", "SELFIE")]:
        conn.exec_driver_sql(
            "INSERT INTO identity_documents VALUES (?,?,?,NULL,NULL)", (ids[k], ids["seller"], t)
        )
    conn.exec_driver_sql(
        "INSERT INTO identity_verifications VALUES (?,?,?, ?,NULL,?,?,'insightface')",
        (ids["identity"], ids["seller"], "2026-01-01", "VERIFIED", ids["front"], ids["selfie"]),
    )
    conn.exec_driver_sql(
        "INSERT INTO account_profiles VALUES (?,1,?,?,?, ?,?)",
        (ids["user"], "VERIFIED", "2026-01-01", "Ahmed Ali", ids["identity"], ids["photo"]),
    )
    conn.exec_driver_sql(
        "INSERT INTO profile_photos VALUES (?,?,?,NULL,?,?,.8,.94)",
        (ids["photo"], ids["user"], "APPROVED", ids["identity"], "insightface"),
    )
    yield conn, ids
    conn.close()
    engine.dispose()


@pytest.mark.parametrize(
    "change",
    [
        "UPDATE account_profiles SET username_locked=0",
        "UPDATE account_profiles SET name_status='REVIEW'",
        "UPDATE profile_photos SET engine='fake'",
        "UPDATE identity_verifications SET face_match_engine='fake'",
        "UPDATE profile_photos SET similarity=.5",
        "UPDATE profile_photos SET deleted_at='2026-01-01'",
        "UPDATE users SET status='SUSPENDED'",
        "UPDATE seller_profiles SET is_flagged=1",
        "UPDATE identity_verifications SET decision_reason='DEMO_FIXTURE_PASS'",
        "UPDATE identity_documents SET extracted_expiry='2020-01-01' WHERE document_type='CNIC_FRONT'",
        "UPDATE identity_verifications SET decision='FAILED'",
    ],
)
def test_eligibility_cannot_be_forged_by_partial_profile(eligibility_db, change):
    conn, ids = eligibility_db
    query = select(m.User.id).where(profile_ready(m.User.id))
    assert len(conn.execute(query).all()) == 1
    conn.exec_driver_sql(change)
    assert conn.execute(query).all() == []


def test_new_identity_invalidates_old_photo_even_same_time(eligibility_db):
    conn, ids = eligibility_db
    conn.exec_driver_sql("UPDATE identity_verifications SET id=?", ("0" * 32,))
    conn.exec_driver_sql("UPDATE account_profiles SET name_identity_id=?", ("0" * 32,))
    conn.exec_driver_sql("UPDATE profile_photos SET identity_id=?", ("0" * 32,))
    assert len(conn.execute(select(m.User.id).where(profile_ready(m.User.id))).all()) == 1
    conn.exec_driver_sql(
        "INSERT INTO identity_verifications SELECT ?,seller_id,created_at,decision,decision_reason,front_document_id,selfie_document_id,face_match_engine FROM identity_verifications",
        ("f" * 32,),
    )
    assert conn.execute(select(m.User.id).where(profile_ready(m.User.id))).all() == []


@pytest.mark.asyncio
async def test_public_payload_excludes_private_name_contact_and_evidence():
    from trustlens.core.domain.enums import VerificationStatus
    from trustlens_api.modules.profiles.service import profile_payload

    uid = uuid4()
    iid = uuid4()
    now = datetime.now(UTC)
    p = NS(
        username_locked=True,
        public_name="Ahmed Ali",
        name_status="VERIFIED",
        name_identity_id=iid,
        approved_photo_id=uuid4(),
        name_encrypted=b"PRIVATE FULL LEGAL NAME",
    )
    user = NS(
        id=uid,
        email="PRIVATE@example.invalid",
        full_name="PRIVATE FULL LEGAL NAME",
        email_verified_at=now,
        created_at=now,
    )
    seller = NS(
        id=uuid4(),
        user_id=uid,
        handle="chosen-once",
        city="Lahore",
        country_code="PK",
        bio="Hello",
        identity_status=VerificationStatus.VERIFIED,
        phone_status=VerificationStatus.VERIFIED,
    )
    photo = NS(
        id=p.approved_photo_id,
        deleted_at=None,
        bucket="PRIVATE_BUCKET",
        object_key="PRIVATE_OBJECT",
    )
    uow = NS(
        session=NS(
            get=AsyncMock(side_effect=[p, photo]),
            execute=AsyncMock(side_effect=[result(True), result(NS(id=iid)), result(True)]),
        ),
        trust_scores=NS(get_current=AsyncMock(return_value=None)),
    )
    data = await profile_payload(uow, NS(), user, seller)
    assert data["displayName"] == "Ahmed Ali" and data["photoMatched"]
    assert not any(
        k in data
        for k in ["email", "phone", "legalName", "extractedName", "nameStatus", "photoReason"]
    )
    assert "PRIVATE" not in repr(data)


@pytest.mark.asyncio
async def test_listing_publication_case_has_postgres_enum_type():
    from sqlalchemy.dialects import postgresql

    from trustlens.core.domain.entities import Listing
    from trustlens.core.domain.enums import ListingSource, ListingStatus
    from trustlens.db.repositories import SqlListingRepository

    session = NS(execute=AsyncMock())
    listing = Listing(
        id=uuid4(),
        seller_id=uuid4(),
        title="Synthetic phone",
        description="Synthetic test",
        status=ListingStatus.ACTIVE,
        source=ListingSource.MANUAL,
        created_at=datetime.now(UTC),
    )
    await SqlListingRepository(session).update(listing)
    sql = str(session.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "CAST(CASE" in sql and "AS listing_status)" in sql
    assert "latest_analysis_id=" in sql  # profile gate must not discard analysis completion


@pytest.mark.asyncio
async def test_background_seller_update_cannot_restore_old_name_or_username():
    from sqlalchemy.dialects import postgresql

    from trustlens.core.domain.entities import SellerProfile
    from trustlens.db.repositories import SqlSellerRepository

    now = datetime.now(UTC)
    session = NS(execute=AsyncMock())
    old = SellerProfile(
        id=uuid4(),
        user_id=uuid4(),
        handle="old-unconfirmed",
        display_name="Old Name",
        account_opened_at=now,
        created_at=now,
    )
    await SqlSellerRepository(session).update(old)
    sql = str(session.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert "display_name=" not in sql and "handle=" not in sql


def test_application_startup_guard_accepts_only_intended_public_profile_routes():
    from trustlens_api.main import app, _assert_routes_are_guarded, _PUBLIC_ROUTES
    _assert_routes_are_guarded(app)
    assert '/api/v1/me/profile' not in _PUBLIC_ROUTES
    assert '/api/v1/admin/profile-name-reviews' not in _PUBLIC_ROUTES
