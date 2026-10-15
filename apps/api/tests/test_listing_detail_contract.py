"""Full repository-to-public-response regression for the listing detail crash."""
from datetime import UTC, datetime
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock
from uuid import uuid4
import pytest
from trustlens.core.domain.enums import ListingStatus, VerificationStatus
from trustlens.core.domain.errors import EntityNotFound
from trustlens.core.application.use_cases.listings import GetPublicListing
from trustlens.db.repositories import SqlListingRepository
from trustlens_api.api.v1.routers import public_listings


def unit_of_work(session):
    uow=NS(listings=SqlListingRepository(session), files=NS(get=AsyncMock(return_value=None)))
    class Uow:
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
    result=Uow();result.__dict__.update(uow.__dict__);return result


@pytest.mark.asyncio
@pytest.mark.parametrize('status',[ListingStatus.ACTIVE,ListingStatus.RESERVED,ListingStatus.SOLD])
async def test_visible_detail_builds_and_serializes_profile_link(monkeypatch,status):
    uid,sid,lid=uuid4(),uuid4(),uuid4()
    listing=NS(id=lid,title='Synthetic phone',description='Synthetic details',price=12000,currency='PKR',category='mobiles',category_node_id=None,category_schema_version=None,category_data={},show_phone=False,condition='used',city='Lahore',area=None,created_at=datetime.now(UTC),status=status,negotiable=False,attributes={'Storage':'128GB'},video_file_id=None,latitude=None,longitude=None)
    seller=NS(id=sid,user_id=uid,handle='synthetic-seller',display_name='Synthetic Seller',identity_status=VerificationStatus.VERIFIED,phone_status=VerificationStatus.VERIFIED)
    row=Mock();row.first.return_value=(listing,seller,None)
    session=NS(execute=AsyncMock(side_effect=[row,[]]))
    uow=unit_of_work(session)
    monkeypatch.setattr(public_listings,'_throttle',AsyncMock())
    response=await public_listings.get_public_listing(lid,NS(),uow,NS(request_id='test'))
    assert response['data']['id']==lid
    assert response['data']['status']==status.value
    assert response['data']['sellerPhotoUrl']==f'/api/v1/public/profiles/{uid}/photo'
    assert response['data']['attributes']=={'Storage':'128GB'}
    assert 'sellerUserId' not in response['data']


@pytest.mark.asyncio
async def test_missing_or_ineligible_detail_remains_not_found():
    row=Mock();row.first.return_value=None
    uow=unit_of_work(NS(execute=AsyncMock(return_value=row)))
    with pytest.raises(EntityNotFound):
        await GetPublicListing(uow=uow).execute(uuid4())
