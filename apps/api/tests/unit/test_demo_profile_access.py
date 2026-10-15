"""Execute the actual eligibility queries against synthetic records."""
from datetime import UTC, datetime
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from trustlens.db import demo_access as d, models as m
from trustlens.db.profiles import marketplace_profile_ready, profile_ready, listing_profile_ready
from test_unified_profiles import eligibility_db, result


@pytest.fixture
def fixture_db(eligibility_db, monkeypatch):
    c, ids = eligibility_db
    monkeypatch.setattr(d, 'local_demo_enabled', lambda: True)
    # Reuse the real strict-verification fixture so it can also prove that the
    # exception cannot silently manufacture name/photo verification.
    r = d.FIXTURES[0]
    for table, col, decl in [
        ('users','email','TEXT'), ('users','created_at','TEXT'),
        ('seller_profiles','external_seller_ref','TEXT'),
    ]:
        c.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN {col} {decl}')
    c.exec_driver_sql('UPDATE users SET id=?,email=?,created_at=?', (r['user_id'].hex,r['email'],'2026-01-01'))
    c.exec_driver_sql('UPDATE seller_profiles SET id=?,user_id=?,external_seller_ref=?', (r['seller_id'].hex,r['user_id'].hex,r['external_ref']))
    c.exec_driver_sql('DELETE FROM account_profiles')
    c.exec_driver_sql('CREATE TABLE demo_profile_access (user_id TEXT,seller_id TEXT,batch TEXT,enrolled_email TEXT,fixture_ref TEXT,account_created_at TEXT,enrolled_at TEXT,enabled BOOLEAN,revoked_at TEXT)')
    c.exec_driver_sql('INSERT INTO demo_profile_access VALUES (?,?,?,?,?,?,?,1,NULL)',
                      (r['user_id'].hex,r['seller_id'].hex,d.BATCH,r['email'],r['external_ref'],'2026-01-01','2026-10-05'))
    c.exec_driver_sql('CREATE TABLE listings (id TEXT,seller_id TEXT)')
    c.exec_driver_sql('INSERT INTO listings VALUES (?,?)',(uuid4().hex,r['seller_id'].hex))
    yield c, r


def test_fixture_access_works_without_faking_real_verification(fixture_db):
    c,r=fixture_db
    assert c.execute(select(m.User.id).where(d.temporary_test_access(m.User.id))).scalars().all()==[r['user_id']]
    assert c.execute(select(m.User.id).where(marketplace_profile_ready(m.User.id))).scalars().all()==[r['user_id']]
    assert not c.execute(select(profile_ready(r['user_id']))).scalar_one()
    assert len(c.execute(select(m.ListingModel.id).where(listing_profile_ready())).all())==1


@pytest.mark.parametrize('change',[
    'UPDATE demo_profile_access SET enabled=0',
    "UPDATE demo_profile_access SET revoked_at='2026-10-06'",
    "UPDATE demo_profile_access SET batch='different'",
    "UPDATE users SET email='new@example.invalid'",
    "UPDATE users SET created_at='2026-10-06'",
    "UPDATE users SET status='SUSPENDED'",
    "UPDATE users SET deleted_at='2026-10-06'",
    'UPDATE seller_profiles SET is_flagged=1',
    "UPDATE seller_profiles SET deleted_at='2026-10-06'",
    "UPDATE seller_profiles SET external_seller_ref='new-fixture'",
    "UPDATE demo_profile_access SET seller_id='11111111111111111111111111111111'",
    'DELETE FROM demo_profile_access',
])
def test_revocation_and_account_changes_deny_access(fixture_db,change):
    c,r=fixture_db
    c.exec_driver_sql(change)
    assert not c.execute(select(d.temporary_test_access(r['user_id']))).scalar_one()
    assert c.execute(select(m.ListingModel.id).where(listing_profile_ready())).all()==[]


def test_new_user_with_same_email_cannot_inherit_exception(fixture_db):
    c,r=fixture_db
    new=uuid4().hex
    c.exec_driver_sql('UPDATE users SET id=?',(new,))
    c.exec_driver_sql('UPDATE seller_profiles SET user_id=?',(new,))
    c.exec_driver_sql('UPDATE demo_profile_access SET user_id=?',(new,))
    assert c.execute(select(m.User.id).where(d.temporary_test_access(m.User.id))).all()==[]


def test_environment_gate_disables_even_enrolled_accounts(fixture_db,monkeypatch):
    c,r=fixture_db
    monkeypatch.setattr(d,'local_demo_enabled',lambda:False)
    assert not c.execute(select(d.temporary_test_access(r['user_id']))).scalar_one()


@pytest.mark.parametrize('environment,host,fake,storage,expected',[
    ('staging','postgres',True,'http://minio:9000',True),
    ('development','localhost',True,'http://localhost:9000',True),
    ('production','postgres',True,'http://minio:9000',False),
    ('staging','remote.example',True,'http://minio:9000',False),
    ('staging','postgres',False,'http://minio:9000',False),
    ('staging','postgres',True,'https://remote.example',False),
])
def test_local_settings_gate(environment,host,fake,storage,expected):
    settings=NS(env=NS(value=environment),ai=NS(use_fake_ai=fake),database=NS(db_echo=False,database_url=f'postgresql+asyncpg://a:b@{host}/test'),storage=NS(storage_provider='s3',storage_endpoint_url=storage))
    assert d.local_demo_enabled(settings)==expected


@pytest.mark.asyncio
async def test_profile_payload_enables_ui_without_a_verified_badge(monkeypatch):
    from trustlens_api.modules.profiles.service import profile_payload
    from trustlens.core.domain.enums import VerificationStatus
    r=d.FIXTURES[0]
    p=NS(username_locked=False,public_name=None,approved_photo_id=None)
    u=NS(id=r['user_id'],email=r['email'],created_at=datetime.now(UTC),email_verified_at=None)
    seller=NS(id=r['seller_id'],handle='test-seller-01',city='Lahore',country_code='PK',bio=None,phone_status=VerificationStatus.VERIFIED)
    uow=NS(session=NS(get=AsyncMock(return_value=p),execute=AsyncMock(side_effect=[result(False),result(True),result(None),result(False)])),trust_scores=NS(get_current=AsyncMock(return_value=None)))
    data=await profile_payload(uow,NS(),u,seller)
    assert data['canInteract'] and data['temporaryTestAccess']
    assert not data['nameVerified'] and not data['photoMatched'] and data['photoUrl'] is None
    assert data['displayName']=='Test Seller 01 (Demo)'
