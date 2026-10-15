"""Offline boundary tests for Replace with AI, with synthetic provider replies."""
import base64
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import ValidationError

from trustlens.core.domain.enums import FilePurpose
from trustlens.core.domain.errors import EntityNotFound
from trustlens_api.assistant.contracts import EnhanceRequest, WebSource
from trustlens_api.assistant.enhance import build_reply, enhance, owned_photos
from trustlens_api.assistant.provider import AssistantConfig, AssistantRateLimited, AssistantUnavailable, GroqProvider, retry_seconds
from trustlens_api.assistant.service import AssistantService


def req(**changes):
    data = dict(title='Samsung S21 Plus', category='mobiles', condition='USED',
                description='6 128 battery good box only no charger')
    return EnhanceRequest(**(data | changes))


def source(**changes):
    data = dict(id=1, title='Samsung S21 Plus specifications', url='https://www.samsung.com/specifications',
                excerpt='Samsung S21 Plus. Display 6.7 inches. Chipset Test Chip. Options: 8 GB RAM. Weight 200 g.', checked_at='2026-10-04')
    return WebSource(**(data | changes))


def row(key, value, evidence, **changes):
    return dict(key=key, value=value, evidence=evidence, origin='seller') | changes


def test_real_screenshot_shorthand_populates_cards_and_retains_exclusion():
    raw = {'specs':[row('RAM','6 GB','6 128'),row('Storage','128 GB','6 128'),
                    row('Battery condition','good','battery good')],
           'seller_points':[{'text':'Box only; no charger included.','evidence':'box only no charger'}]}
    result = build_reply(req(),raw,[],[],0)
    assert {s.key:s.value for s in result.specs} == {'RAM':'6 GB','Storage':'128 GB','Battery condition':'good'}
    assert 'no charger' in result.description
    assert '100%' not in result.description and 'Camera' not in result.description


def test_only_exact_supported_factory_specs_and_no_unit_claims():
    raw={'specs':[row('Display','6.7 inches','Display 6.7 inches',origin='source',source_id=1,model='Samsung S21 Plus'),
                  row('RAM','8 GB','8 GB RAM',origin='source',source_id=1,model='Samsung S21 Plus'),
                  row('PTA','Approved','Display 6.7 inches',origin='source',source_id=1,model='Samsung S21 Plus'),
                  row('Camera','200 MP','200 MP camera',origin='source',source_id=1,model='Samsung S21 Plus'),
                  row('Weight','200 g','Weight 200 g',origin='source',source_id=999,model='Samsung S21 Plus')]}
    result=build_reply(req(),raw,[source()],[],0)
    assert [(s.key,s.value) for s in result.specs] == [('Display','6.7 inches')]
    assert len(result.sources)==1


@pytest.mark.parametrize('title,model,url',[
    ('Samsung S21 Ultra','Samsung S21','https://samsung.com/specs'),
    ('Samsung S21 Plus','Samsung S21 Plus','https://samsung.com.evil.example/specs'),
    ('LG 9kg','LG','https://lg.com/specs'),
])
def test_wrong_variant_and_untrusted_sources_not_added(title,model,url):
    raw={'specs':[row('Display','6.7 inches','Display 6.7 inches',origin='source',source_id=1,model=model)]}
    assert not build_reply(req(title=title),raw,[source(url=url)],[],0).specs


def test_existing_values_and_aliases_are_preserved():
    request=req(facts={'Storage':'256 GB','Colour':'Olive'})
    raw={'specs':[row('ROM','128 GB','6 128'), row('Color','Blue','Blue')]}
    result=build_reply(request,raw,[],[],0)
    assert {s.key:s.value for s in result.specs}==request.facts


@pytest.mark.parametrize('text',['Face ID not working; screen replaced; no charger.', 'x'*940+' damaged screen; no charger.'])
def test_faults_are_never_cut_off_to_fit_specs(text):
    result=build_reply(req(description=text),{'seller_points':[{'text':'Perfect working phone.','evidence':text}],
                      'specs':[]},[],[],0)
    assert text in result.description
    assert len(result.description)<=8000
    assert 'Perfect working' not in result.description


def test_numbers_cannot_be_invented_in_rewrite():
    result=build_reply(req(description='battery good'),{'seller_points':[{'text':'Battery health 100%.','evidence':'battery good'}]},[],[],0)
    assert '100%' not in result.description and 'battery good' in result.description


def test_photo_observations_never_become_published_fields():
    raw={'specs':[row('PTA','Approved','photo',origin='photo')],'photo_hints':['Photo may show a different model.']}
    result=build_reply(req(),raw,[],[],2)
    assert not result.specs and 'Approved' not in result.description
    assert result.photo_hints and result.photos_checked==2
    assert not build_reply(req(),raw,[],[],0).photo_hints


@pytest.mark.parametrize('category,description,key,value',[
    ('computers','16 GB RAM and 512 GB SSD','RAM','16 GB'),
    ('home-appliances','capacity 9 kg; drain hose missing','Capacity','9 kg'),
    ('vehicles','Mileage 60000 km; bumper repainted','Mileage','60000 km'),
    ('property-rent','2 bedrooms; unfurnished','Bedrooms','2'),
    ('furniture','wood table, scratched top','Material','wood'),
])
def test_categories_use_seller_specific_details(category,description,key,value):
    result=build_reply(req(category=category,description=description),{'specs':[row(key,value,description)]},[],[],0)
    assert any(x.key==key and x.value==value for x in result.specs)
    assert description in result.description


class Uow:
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass


def photo_container(owner=True,purpose=FilePurpose.LISTING_IMAGE):
    seller=SimpleNamespace(id=uuid4(),user_id=uuid4())
    listing=SimpleNamespace(seller_id=seller.id if owner else uuid4())
    file=SimpleNamespace(purpose=purpose,owner_user_id=seller.user_id,deleted_at=None,
                        size_bytes=500,mime_type='image/jpeg',bucket='listings',object_key='only-photo')
    uow=Uow();uow.listings=SimpleNamespace(get=AsyncMock(return_value=listing),
          list_images=AsyncMock(return_value=[SimpleNamespace(position=0,file_id=uuid4())]))
    uow.files=SimpleNamespace(get=AsyncMock(return_value=file))
    out=BytesIO();Image.new('RGB',(10,10),'white').save(out,format='JPEG')
    container=SimpleNamespace(uow=lambda:uow,storage=SimpleNamespace(get=AsyncMock(return_value=out.getvalue())))
    return container,seller


async def test_other_sellers_photos_are_rejected_before_read():
    container,seller=photo_container(owner=False)
    with pytest.raises(EntityNotFound):await owned_photos(container,req(listing_id=uuid4()),seller)
    container.storage.get.assert_not_called()


async def test_private_identity_files_cannot_enter_photo_analysis():
    container,seller=photo_container(purpose='IDENTITY_DOCUMENT')
    images,warnings=await owned_photos(container,req(listing_id=uuid4()),seller)
    assert images==[] and warnings
    container.storage.get.assert_not_called()


async def test_owned_photo_is_resized_and_no_storage_url_leaves_server():
    container,seller=photo_container()
    images,warnings=await owned_photos(container,req(listing_id=uuid4()),seller)
    assert not warnings and images[0].startswith('data:image/jpeg;base64,')
    assert 'only-photo' not in images[0]
    decoded=Image.open(BytesIO(base64.b64decode(images[0].split(',',1)[1])))
    assert max(decoded.size)<=768 and not decoded.getexif()


async def test_failed_optional_research_still_enhances_written_details():
    async with httpx.AsyncClient() as client:
        service=AssistantService(SimpleNamespace(),client,AssistantConfig(enabled=True,api_key='fixture'))
        service.web=AsyncMock(side_effect=AssistantUnavailable('Search not configured'))
        service.allowance=AsyncMock()
        service.provider.complete=AsyncMock(return_value={'specs':[row('Storage','128 GB','6 128')]})
        result=await enhance(service,req(),SimpleNamespace())
        assert result.specs and result.warnings
        service.provider.complete.assert_awaited_once()
        assert service.provider.complete.call_args.args[1]['seller_description']==req().description


async def test_provider_retry_after_is_safe_and_vision_uses_supported_model():
    calls=[]
    def transport(request):
        calls.append(__import__('json').loads(request.content))
        return httpx.Response(429,headers={'Retry-After':'17'},json={'error':'private diagnostics'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as client:
        provider=GroqProvider(AssistantConfig(enabled=True,api_key='fixture'),client)
        with pytest.raises(AssistantRateLimited) as error:
            await provider.complete('JSON',{},images=['data:image/jpeg;base64,Zg=='])
        assert error.value.retry_after==17 and 'private' not in str(error.value)
    assert calls[0]['model']=='qwen/qwen3.8-27b' and calls[0]['reasoning_effort']=='none'
    assert retry_seconds('nan')==60 and retry_seconds('infinity')==60


def test_route_retains_local_limit_and_retry_after_header(monkeypatch):
    from trustlens_api.api.deps import get_current_actor,get_container,get_request_meta
    from trustlens_api.api.v1.routers.assistant import router
    from trustlens_api.exceptions.handlers import register_exception_handlers
    app=FastAPI();app.include_router(router,prefix='/api/v1');register_exception_handlers(app)
    limiter=SimpleNamespace(hit=AsyncMock(return_value=(False,0,23)))
    app.dependency_overrides[get_current_actor]=lambda:SimpleNamespace(user_id=uuid4())
    app.dependency_overrides[get_container]=lambda:SimpleNamespace(rate_limiter=limiter)
    app.dependency_overrides[get_request_meta]=lambda:SimpleNamespace(ip='127.0.0.1',request_id='test')
    monkeypatch.setenv('TRUSTLENS_CHAT_PER_MINUTE','4')
    with TestClient(app) as client:response=client.post('/api/v1/assistant/enhance',json=req().model_dump(mode='json'))
    assert response.status_code==429 and response.headers['retry-after']=='23'
    assert limiter.hit.call_args.kwargs['limit']==4


def test_authenticated_route_and_bounded_inputs():
    from trustlens_api.main import _assert_routes_are_guarded,create_app
    _assert_routes_are_guarded(create_app())
    with pytest.raises(ValidationError):req(description='x'*8001)
    with pytest.raises(ValidationError):req(facts={'password':'never send'})


async def test_successful_route_closes_seller_database_session_before_ai(monkeypatch):
    from trustlens_api.api.deps import get_current_actor, get_container, get_request_meta
    from trustlens_api.api.v1.routers import assistant
    closed=[]
    class SellerUow(Uow):
        async def __aexit__(self, *args): closed.append(True)
    uow=SellerUow()
    uow.sellers=SimpleNamespace(get_by_user=AsyncMock(return_value=SimpleNamespace(id=uuid4())))
    container=SimpleNamespace(uow=lambda:uow, rate_limiter=SimpleNamespace(hit=AsyncMock(return_value=(True,3,0))))
    async def mocked_enhance(service, request, seller):
        assert closed
        return build_reply(request,{'specs':[row('Storage','128 GB','6 128')]},[],[],0)
    monkeypatch.setattr(assistant,'enhance',mocked_enhance)
    app=FastAPI();app.include_router(assistant.router,prefix='/api/v1')
    app.dependency_overrides[get_current_actor]=lambda:SimpleNamespace(user_id=uuid4())
    app.dependency_overrides[get_container]=lambda:container
    app.dependency_overrides[get_request_meta]=lambda:SimpleNamespace(ip='127.0.0.1',request_id='test')
    with TestClient(app) as client:
        response=client.post('/api/v1/assistant/enhance',json=req().model_dump(mode='json',by_alias=True))
    assert response.status_code==200,response.text
    data=response.json()['data']
    assert data['specs']==[{'key':'Storage','value':'128 GB'}]
    assert 'no charger' in data['description']
    assert 'photoHints' in data and 'missingDetails' in data
