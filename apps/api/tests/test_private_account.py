"""Regression coverage and test support for test private account."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import date,timedelta
import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from trustlens_api.api.v1.routers.private_account import PrivateSettings,read_private_settings,write_private_settings
from trustlens_api.api.v1.schemas.public_listing import PublicListingDetailResponse
from trustlens.core.domain.errors import ConflictError

@pytest.mark.parametrize('value',['2026-02-30','1800-01-01',(date.today()+timedelta(days=1)).isoformat()])
def test_birth_date_validation(value):
    with pytest.raises(ValidationError):PrivateSettings(date_of_birth=value)

def test_private_attributes_not_accepted_by_public_listing_contract():
    assert not {'date_of_birth','gender','addresses'} & PublicListingDetailResponse.model_fields.keys()

@pytest.mark.asyncio
async def test_private_read_scoped_to_authenticated_owner():
    user=uuid4();execute=AsyncMock(return_value=NS(scalar_one_or_none=lambda:None));uow=NS(session=NS(execute=execute))
    reply=await read_private_settings(NS(user_id=user),uow,NS(request_id='synthetic'))
    compiled=execute.await_args.args[0].compile(dialect=postgresql.dialect())
    assert user in compiled.params.values()
    assert 'private_account_settings.user_id =' in str(compiled)
    assert reply['data']['addresses']==[] and reply['data']['version']==0

@pytest.mark.asyncio
async def test_settings_write_retains_private_data_and_does_not_take_an_owner_from_body():
    uid=uuid4();body=PrivateSettings(date_of_birth='2000-02-29',addresses=[{'label':'Home','city':'Lahore','addressLine':'Synthetic private address'}])
    uow=NS(session=NS(execute=AsyncMock(return_value=NS(rowcount=1))),commit=AsyncMock())
    reply=await write_private_settings(body,NS(user_id=uid),uow,NS(request_id='synthetic'))
    compiled=uow.session.execute.await_args.args[0].compile(dialect=postgresql.dialect())
    assert compiled.params['user_id']==uid
    assert reply['data']['addresses'][0]['id'] and reply['data']['version']==1
    with pytest.raises(ValidationError):PrivateSettings(userId=str(uuid4()))

@pytest.mark.asyncio
async def test_stale_settings_do_not_overwrite_other_tab():
    uow=NS(session=NS(execute=AsyncMock(return_value=NS(rowcount=0))),commit=AsyncMock())
    with pytest.raises(ConflictError):await write_private_settings(PrivateSettings(version=2),NS(user_id=uuid4()),uow,NS(request_id='synthetic'))
    uow.commit.assert_not_awaited()
