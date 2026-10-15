"""Owner-only optional personal details. Never joined into a public projection."""
from datetime import date
from typing import Any, Literal
from uuid import UUID, uuid4
from fastapi import APIRouter
from pydantic import Field, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from trustlens.db.models import PrivateAccountSettingsModel
from trustlens.core.domain.errors import ConflictError
from trustlens_api.api.deps import ActorDep, UowDep, MetaDep
from trustlens_api.api.v1.schemas.common import Schema, envelope

router=APIRouter(prefix='/me/private-settings',tags=['Account'])

class PrivateAddress(Schema):
    id: UUID | None = None
    label: str = Field(min_length=1,max_length=60)
    province: str = Field(default="",max_length=80)
    city: str = Field(min_length=1,max_length=80)
    area: str = Field(default='',max_length=120)
    address_line: str = Field(min_length=5,max_length=300)

class PrivateSettings(Schema):
    date_of_birth: str | None = None
    gender: Literal['Woman','Man','Non-binary','Self-described','Prefer not to say'] | None = None
    addresses: list[PrivateAddress] = Field(default_factory=list,max_length=10)
    version: int = Field(default=0,ge=0)

    @field_validator('date_of_birth')
    @classmethod
    def valid_birth_date(cls,value):
        if value is None:return None
        try:parsed=date.fromisoformat(value)
        except ValueError:raise ValueError('Use a valid YYYY-MM-DD birth date.') from None
        if parsed.isoformat()!=value or parsed>date.today() or parsed.year<1900:
            raise ValueError('Use a birth date between 1900 and today.')
        return value

    @model_validator(mode='after')
    def unique_addresses(self):
        ids=[address.id for address in self.addresses if address.id is not None]
        if len(set(ids))!=len(ids):raise ValueError('Address IDs must be unique.')
        return self

@router.get('')
async def read_private_settings(actor:ActorDep,uow:UowDep,meta:MetaDep)->dict[str,Any]:
    row=(await uow.session.execute(select(PrivateAccountSettingsModel).where(PrivateAccountSettingsModel.user_id==actor.user_id))).scalar_one_or_none()
    data=PrivateSettings(date_of_birth=row.date_of_birth,gender=row.gender,addresses=row.addresses,version=row.version) if row else PrivateSettings()
    return envelope(data.model_dump(mode='json',by_alias=True),request_id=meta.request_id)

@router.put('')
async def write_private_settings(body:PrivateSettings,actor:ActorDep,uow:UowDep,meta:MetaDep)->dict[str,Any]:
    # The owner comes only from authentication; IDs in the body identify local
    # address rows and are never used to access another account's data.
    addresses=[a.model_copy(update={'id':a.id or uuid4()}).model_dump(mode='json',by_alias=True) for a in body.addresses]
    values={'date_of_birth':body.date_of_birth,'gender':body.gender,'addresses':addresses,'version':body.version+1}
    stmt=insert(PrivateAccountSettingsModel).values(user_id=actor.user_id,**values)
    if body.version==0:stmt=stmt.on_conflict_do_nothing(index_elements=['user_id'])
    else:
        from sqlalchemy import update
        stmt=update(PrivateAccountSettingsModel).where(PrivateAccountSettingsModel.user_id==actor.user_id,PrivateAccountSettingsModel.version==body.version).values(**values)
    result=await uow.session.execute(stmt)
    if result.rowcount!=1:raise ConflictError('These settings changed in another tab. Reload before saving again.')
    await uow.commit()
    return envelope(PrivateSettings(**values).model_dump(mode='json',by_alias=True),request_id=meta.request_id)
