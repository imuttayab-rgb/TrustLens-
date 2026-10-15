"""Regression coverage and test support for test marketplace account security."""
from datetime import UTC, datetime
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
import pytest
from fastapi import Response
from trustlens.core.application.use_cases.auth.authenticate import AuthenticateWithGoogle, GoogleAuthCommand
from trustlens.core.domain.entities import User
from trustlens.core.domain.enums import AccountStatus, UserRole
from trustlens.core.domain.errors import MfaRequired, TokenInvalid
from trustlens.core.domain.value_objects import Email
from trustlens_api.api.v1.routers.auth import google_verify_mfa, GoogleMfaRequest, list_sessions, revoke_session
from trustlens_api.api.deps import get_optional_actor

NOW=datetime.now(UTC)

def context(user):
    uow=MagicMock();uow.__aenter__=AsyncMock(return_value=uow);uow.__aexit__=AsyncMock(return_value=False)
    uow.users=NS(get_by_email=AsyncMock(return_value=user),record_successful_login=AsyncMock())
    uow.commit=AsyncMock()
    return uow

@pytest.mark.asyncio
@pytest.mark.parametrize('enabled,role,required',[(True,UserRole.BUYER,frozenset()),(False,UserRole.ADMIN,frozenset({UserRole.ADMIN}))])
async def test_google_cannot_bypass_enrolled_or_role_required_mfa(enabled,role,required):
    user=User(id=uuid4(),email=Email('synthetic@example.test'),full_name='Synthetic',status=AccountStatus.ACTIVE,primary_role=role,created_at=NOW,email_verified_at=NOW,mfa_enabled=enabled)
    uow=context(user)
    with patch('trustlens.core.application.use_cases.auth.authenticate._new_session',AsyncMock()) as issue:
        with pytest.raises(MfaRequired):
            await AuthenticateWithGoogle(uow=uow,tokens=MagicMock(),clock=NS(now=lambda:NOW),ids=MagicMock(),mfa_required_roles=required).execute(GoogleAuthCommand(email=user.email.value,full_name=user.full_name))
        issue.assert_not_awaited()

@pytest.mark.asyncio
async def test_google_mfa_requires_browser_challenge_cookie():
    with pytest.raises(TokenInvalid):
        await google_verify_mfa(GoogleMfaRequest(code='123456'),Response(),None,None,None,None)

@pytest.mark.asyncio
async def test_deleted_account_cannot_use_existing_access_token():
    request=NS(headers={'authorization':'Bearer synthetic'})
    container=NS(jwt=NS(decode=lambda _: {'typ':'access','sub':str(uuid4())}))
    uow=NS(users=NS(session_allowed=AsyncMock(return_value=False)))
    with pytest.raises(TokenInvalid):await get_optional_actor(request,container,uow)

@pytest.mark.asyncio
async def test_session_list_uses_the_revocable_family_id():
    family=uuid4();user=uuid4();token=NS(id=uuid4(),family_id=family,created_at=NOW,expires_at=NOW,user_agent=None,ip_address=None)
    actor=NS(user_id=user,session_id=family);uow=NS(refresh_tokens=NS(list_active_for_user=AsyncMock(return_value=[token])))
    result=await list_sessions(actor,uow,NS(request_id='test'))
    assert result['data'][0]['id']==family
    assert result['data'][0]['isCurrent'] is True

@pytest.mark.asyncio
async def test_other_accounts_session_family_cannot_be_revoked():
    from trustlens.core.domain.errors import EntityNotFound
    uow=NS(refresh_tokens=NS(list_active_for_user=AsyncMock(return_value=[]),revoke_family=AsyncMock()))
    with pytest.raises(EntityNotFound):
        await revoke_session(str(uuid4()),NS(user_id=uuid4()),uow,NS(request_id='test'),NS(clock=NS(now=lambda:NOW)))
    uow.refresh_tokens.revoke_family.assert_not_awaited()


@pytest.mark.parametrize('raw',['https://evil.invalid','//evil.invalid','/\\evil.invalid','/%2fevil.invalid','/%255cevil.invalid','/\nevil.invalid'])
def test_google_return_rejects_external_and_encoded_redirects(raw):
    from trustlens_api.api.v1.routers.auth import _safe_return_path
    assert _safe_return_path(raw)=='/dashboard'


@pytest.mark.asyncio
@pytest.mark.parametrize('mfa',[False,True])
async def test_google_callback_preserves_sell_destination_without_bypassing_mfa(mfa):
    from urllib.parse import parse_qs, urlsplit
    from trustlens_api.api.v1.routers import auth
    container=NS(settings=NS(web_base_url='https://trustlens.example',google_auth=NS(),
                            env=NS(is_deployed=True),security=NS(refresh_token_ttl_days=30,mfa_required_roles=[])),
                 token_hasher=NS(),clock=NS(),ids=NS())
    session=NS(refresh_token_raw='synthetic',expires_at=NOW)
    execute=AsyncMock(side_effect=MfaRequired(uuid4())) if mfa else AsyncMock(return_value=session)
    with patch.object(auth,'exchange_code',AsyncMock(return_value=NS(email='test@example.test',name='Test'))), \
         patch.object(auth,'AuthenticateWithGoogle',return_value=NS(execute=execute)), \
         patch.object(auth,'_issue_mfa_challenge',AsyncMock(return_value={'data':{'mfaToken':'synthetic-challenge'}})), \
         patch.object(auth,'set_refresh_cookie') as refresh:
        result=await auth.google_callback(container,NS(),NS(ip=None,user_agent=None),code='code',state='same',tl_oauth_state='same',tl_oauth_next='/dashboard/listings/new?draft=abc')
    url=urlsplit(result.headers['location'])
    assert url.netloc=='trustlens.example'
    if mfa:
        assert url.path=='/login'
        assert parse_qs(url.query)['next']==['/dashboard/listings/new?draft=abc']
        refresh.assert_not_called()
        assert any('tl_google_mfa=' in v and 'HttpOnly' in v and 'Secure' in v for v in result.headers.getlist('set-cookie'))
    else:
        assert url.path=='/dashboard/listings/new' and url.query=='draft=abc'
        refresh.assert_called_once()
    assert any('tl_oauth_next=' in v and 'Max-Age=0' in v for v in result.headers.getlist('set-cookie'))
