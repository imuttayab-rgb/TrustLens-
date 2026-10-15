"""Regression coverage and test support for test marketplace completion."""
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pytest
from pydantic import ValidationError as PydanticError
from sqlalchemy.dialects import postgresql
from sqlalchemy import select
from trustlens.core.catalogue import CATALOGUE, NODES, required_category_details, typed_attributes
from trustlens.core.catalogue.recommendations import recommendation_plan, same_search
from trustlens.core.domain.errors import EntityNotFound, ValidationError
from trustlens_api.api.v1.routers import public_listings as routes
from trustlens_api.api.v1.routers.messaging import SetImportantRequest, set_conversation_important


def test_all_categories_have_localized_typed_fields_and_guidance():
    for n in NODES.values():
        if n['selectable']:
            assert n['schema']!='general'
            assert n['labelUr']!=n['label']
            assert CATALOGUE['schemas'][n['schema']]
            assert CATALOGUE['guidance'][n['schema']]
            assert CATALOGUE['guidanceUr'][n['schema']]


def test_transfer_media_exception_is_narrow_and_requires_seller_assertions():
    for n in NODES.values():
        if n['policy']=='transfer':
            assert n['id']=='mobiles/mobile-numbers' or n['id'].startswith('business-industrial-agriculture/business-for-sale')
            assert 'Authority to offer transfer' in required_category_details(n['id'],{})
    assert NODES['mobiles/mobile-phones']['policy']=='physical'
    assert typed_attributes('business-industrial-agriculture/agriculture/seeds',{'Quantity':'10','Quantity unit':'kg'})=={'quantity':10.0,'quantity_unit':'kg'}


def test_related_groups_respect_variants_and_explicit_compatibility():
    plans=recommendation_plan('mobiles/mobile-phones',{'model':'S21+','brand':'Samsung'},None,detail=True)
    assert [p.key for p in plans]==['same-model','same-family','alternatives','compatible-accessories']
    assert plans[0].facets=={'model':'S21+','brand':'Samsung'}
    assert plans[-1].facets=={'compatible_model':'S21+'}
    assert not any(p.key=='compatible-accessories' for p in recommendation_plan('mobiles/mobile-phones',{},'Samsung',detail=False))
    assert same_search('Samsung S 21 Plus used','Samsung S21+')
    assert not same_search('Samsung S21 Ultra','Samsung S21+')


@pytest.mark.asyncio
@pytest.mark.parametrize('participants', [None,'other'])
async def test_important_cannot_modify_another_users_conversation(participants):
    uid=uuid4(); cid=uuid4()
    uow=NS(messaging=NS(get_participants=AsyncMock(return_value=None if participants is None else (uuid4(),uuid4()))),session=NS(execute=AsyncMock()),commit=AsyncMock())
    with pytest.raises(EntityNotFound):await set_conversation_important(cid,SetImportantRequest(important=True),NS(user_id=uid),uow,NS(request_id='test'))
    uow.session.execute.assert_not_awaited();uow.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_important_is_persisted_for_only_the_authenticated_participant():
    uid=uuid4();cid=uuid4()
    uow=NS(messaging=NS(get_participants=AsyncMock(return_value=(uid,uuid4()))),session=NS(execute=AsyncMock()),commit=AsyncMock())
    result=await set_conversation_important(cid,SetImportantRequest(important=True),NS(user_id=uid),uow,NS(request_id='test'))
    stmt=uow.session.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert stmt.params['user_id']==uid and stmt.params['conversation_id']==cid
    assert result['data']['important'] is True;uow.commit.assert_awaited_once()


@pytest.mark.parametrize('data',[{'important':'true'},{'important':1},{'important':True,'userId':'other'}])
def test_important_rejects_coercion_and_overposting(data):
    with pytest.raises(PydanticError):SetImportantRequest(**data)


@pytest.mark.asyncio
async def test_live_model_options_are_parent_scoped_and_reject_private_fields():
    repo=NS(category_field_options=AsyncMock(return_value=['S21+']))
    with patch.object(routes,'_throttle',AsyncMock()):
        response=await routes.catalogue_options(NS(),NS(listings=repo),NS(request_id='test'),'mobiles/mobile-phones','model','Samsung','S21')
        assert response['data']==['S21+']
        repo.category_field_options.assert_awaited_once_with('mobiles/mobile-phones','model',parent_key='brand',parent_value='Samsung',query='S21')
        with pytest.raises(ValidationError):await routes.catalogue_options(NS(),NS(listings=repo),NS(request_id='test'),'mobiles/mobile-phones','password',None,'')


def test_inbox_queries_compile_with_private_preference_scope_and_verified_public_name():
    from trustlens.db.repositories import SqlMessagingRepository
    from trustlens.db import models as m
    uid=uuid4();repo=SqlMessagingRepository(NS())
    base=select(m.ConversationModel.id).join(m.SellerProfile,m.SellerProfile.id==m.ConversationModel.seller_id).where((m.ConversationModel.buyer_id==uid)|(m.SellerProfile.user_id==uid))
    for folder in ['all','buying','selling','unread','important']:
        query=repo._conversation_filters(base,uid,folder,'50%_test')
        compiled=query.compile(dialect=postgresql.dialect())
        sql=str(compiled)
        assert 'full_name' not in sql and 'public_name' in sql
        assert any('50\\%\\_test' in str(v) for v in compiled.params.values())
        if folder=='important':assert 'conversation_preferences.user_id' in sql
