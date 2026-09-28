"""SQLAlchemy repository implementations.

Each one satisfies the corresponding Protocol in `trustlens.core.domain.ports`
structurally - there is no inheritance link, which is what keeps the dependency
arrow pointing inward (ADR-0004).

Soft-delete filtering lives here, in `_alive()`, rather than being remembered
at every call site. That is the difference between an invariant and a habit.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import Select, and_, delete, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from trustlens.core.domain import entities as ent
from trustlens.core.domain import enums as e
from trustlens.core.domain.value_objects import Email, PhoneE164
from trustlens.db import mappers as map_
from trustlens.db import models as m


def _alive(stmt: Select[Any], model: Any) -> Select[Any]:
    """Apply the soft-delete filter. Applied centrally, never per call site."""
    return stmt.where(model.deleted_at.is_(None))


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    def _with_roles(self, stmt: Select[Any]) -> Select[Any]:
        return stmt.options(
            selectinload(m.User.roles)
            .selectinload(m.UserRoleLink.role)
            .selectinload(m.Role.permissions)
            .selectinload(m.RolePermission.permission)
        )

    async def get(self, user_id: UUID) -> ent.User | None:
        stmt = self._with_roles(_alive(select(m.User), m.User).where(m.User.id == user_id))
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_user(row) if row else None

    async def get_by_email(self, email: Email) -> ent.User | None:
        stmt = self._with_roles(_alive(select(m.User), m.User).where(m.User.email == email.value))
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_user(row) if row else None

    async def get_password_hash(self, user_id: UUID) -> str | None:
        return (
            await self._s.execute(select(m.User.password_hash).where(m.User.id == user_id))
        ).scalar_one_or_none()

    async def create(self, *, user: ent.User, password_hash: str | None) -> ent.User:
        row = m.User(
            id=user.id,
            email=user.email.value,
            full_name=user.full_name,
            status=user.status,
            primary_role=user.primary_role,
            password_hash=password_hash,
            created_at=user.created_at,
            updated_at=user.created_at,
        )
        self._s.add(row)
        await self._s.flush()
        for role_key in user.roles or {user.primary_role}:
            await self.assign_role(user.id, role_key.value, granted_by=None)
        return user

    async def update(self, user: ent.User) -> ent.User:
        await self._s.execute(
            update(m.User)
            .where(m.User.id == user.id)
            .values(
                full_name=user.full_name,
                status=user.status,
                primary_role=user.primary_role,
                mfa_enabled=user.mfa_enabled,
                version=m.User.version + 1,
            )
        )
        return user

    async def set_password_hash(self, user_id: UUID, password_hash: str) -> None:
        await self._s.execute(
            update(m.User)
            .where(m.User.id == user_id)
            .values(password_hash=password_hash, password_changed_at=func.now())
        )

    async def get_mfa_secret(self, user_id: UUID) -> bytes | None:
        return (
            await self._s.execute(select(m.User.mfa_secret_encrypted).where(m.User.id == user_id))
        ).scalar_one_or_none()

    async def set_mfa_secret(self, user_id: UUID, secret_encrypted: bytes | None) -> None:
        await self._s.execute(
            update(m.User).where(m.User.id == user_id).values(mfa_secret_encrypted=secret_encrypted)
        )

    async def record_failed_login(self, user_id: UUID, *, locked_until: datetime | None) -> None:
        await self._s.execute(
            update(m.User)
            .where(m.User.id == user_id)
            .values(
                failed_login_count=m.User.failed_login_count + 1,
                locked_until=locked_until,
            )
        )

    async def record_successful_login(self, user_id: UUID, *, at: datetime) -> None:
        await self._s.execute(
            update(m.User)
            .where(m.User.id == user_id)
            .values(failed_login_count=0, locked_until=None, last_login_at=at)
        )

    async def mark_email_verified(self, user_id: UUID, *, at: datetime) -> None:
        await self._s.execute(
            update(m.User)
            .where(m.User.id == user_id)
            .values(email_verified_at=at, status=e.AccountStatus.ACTIVE)
        )

    async def assign_role(self, user_id: UUID, role_key: str, *, granted_by: UUID | None) -> None:
        role_id = (
            await self._s.execute(select(m.Role.id).where(m.Role.key == role_key))
        ).scalar_one_or_none()
        if role_id is None:
            return
        exists = (
            await self._s.execute(
                select(m.UserRoleLink).where(
                    m.UserRoleLink.user_id == user_id, m.UserRoleLink.role_id == role_id
                )
            )
        ).scalar_one_or_none()
        if exists is None:
            self._s.add(m.UserRoleLink(user_id=user_id, role_id=role_id, granted_by=granted_by))

    async def list_permissions(self, user_id: UUID) -> frozenset[str]:
        rows = await self._s.execute(
            select(m.Permission.key)
            .join(m.RolePermission, m.RolePermission.permission_id == m.Permission.id)
            .join(m.UserRoleLink, m.UserRoleLink.role_id == m.RolePermission.role_id)
            .where(m.UserRoleLink.user_id == user_id)
        )
        return frozenset(rows.scalars().all())


class SqlSellerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, seller_id: UUID) -> ent.SellerProfile | None:
        row = (
            await self._s.execute(
                _alive(select(m.SellerProfile), m.SellerProfile).where(
                    m.SellerProfile.id == seller_id
                )
            )
        ).scalar_one_or_none()
        return map_.to_seller(row) if row else None

    async def get_by_user(self, user_id: UUID) -> ent.SellerProfile | None:
        row = (
            await self._s.execute(
                _alive(select(m.SellerProfile), m.SellerProfile).where(
                    m.SellerProfile.user_id == user_id
                )
            )
        ).scalar_one_or_none()
        return map_.to_seller(row) if row else None

    async def get_by_handle(self, handle: str) -> ent.SellerProfile | None:
        row = (
            await self._s.execute(
                _alive(select(m.SellerProfile), m.SellerProfile).where(
                    m.SellerProfile.handle == handle
                )
            )
        ).scalar_one_or_none()
        return map_.to_seller(row) if row else None

    async def get_by_external_ref(
        self, *, marketplace_slug: str, external_ref: str
    ) -> ent.SellerProfile | None:
        row = (
            await self._s.execute(
                _alive(select(m.SellerProfile), m.SellerProfile)
                .join(m.Marketplace, m.Marketplace.id == m.SellerProfile.marketplace_id)
                .where(
                    m.Marketplace.slug == marketplace_slug,
                    m.SellerProfile.external_seller_ref == external_ref,
                )
            )
        ).scalar_one_or_none()
        return map_.to_seller(row) if row else None

    async def create(self, seller: ent.SellerProfile) -> ent.SellerProfile:
        self._s.add(
            m.SellerProfile(
                id=seller.id,
                user_id=seller.user_id,
                handle=seller.handle,
                display_name=seller.display_name,
                account_opened_at=seller.account_opened_at,
                marketplace_id=seller.marketplace_id,
                external_seller_ref=seller.external_seller_ref,
                business_type=seller.business_type,
                city=seller.city,
                country_code=seller.country_code,
                identity_status=seller.identity_status,
                phone_status=seller.phone_status,
                email_status=seller.email_status,
                account_type=seller.account_type,
                business_legal_name=seller.business_legal_name,
                business_registration_number=seller.business_registration_number,
                business_document_file_id=seller.business_document_file_id,
                business_verification_status=seller.business_verification_status,
                created_at=seller.created_at,
                updated_at=seller.created_at,
            )
        )
        await self._s.flush()
        return seller

    async def update(self, seller: ent.SellerProfile) -> ent.SellerProfile:
        await self._s.execute(
            update(m.SellerProfile)
            .where(m.SellerProfile.id == seller.id)
            .values(
                display_name=seller.display_name,
                business_type=seller.business_type,
                city=seller.city,
                country_code=seller.country_code,
                bio=seller.bio,
                current_trust_score_id=seller.current_trust_score_id,
                identity_status=seller.identity_status,
                phone_status=seller.phone_status,
                email_status=seller.email_status,
                account_type=seller.account_type,
                business_legal_name=seller.business_legal_name,
                business_registration_number=seller.business_registration_number,
                business_document_file_id=seller.business_document_file_id,
                business_verification_status=seller.business_verification_status,
                is_flagged=seller.is_flagged,
                version=m.SellerProfile.version + 1,
            )
        )
        return seller

    async def list_stale_scores(self, *, before: datetime, limit: int) -> list[UUID]:
        """Sellers whose current score has expired, for the nightly sweep."""
        rows = await self._s.execute(
            select(m.SellerProfile.id)
            .join(
                m.TrustScoreModel,
                (m.TrustScoreModel.seller_id == m.SellerProfile.id) & m.TrustScoreModel.is_current,
                isouter=True,
            )
            .where(
                m.SellerProfile.deleted_at.is_(None),
                (m.TrustScoreModel.id.is_(None)) | (m.TrustScoreModel.valid_until < before),
            )
            .limit(limit)
        )
        return list(rows.scalars().all())

    async def handle_exists(self, handle: str) -> bool:
        return bool(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.SellerProfile)
                    .where(m.SellerProfile.handle == handle)
                )
            ).scalar_one()
        )


class SqlIdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_document(self, document_id: UUID) -> ent.IdentityDocument | None:
        row = await self._s.get(m.IdentityDocumentModel, document_id)
        return map_.to_identity_document(row) if row else None

    async def list_documents(self, seller_id: UUID) -> list[ent.IdentityDocument]:
        rows = await self._s.execute(
            _alive(select(m.IdentityDocumentModel), m.IdentityDocumentModel)
            .where(m.IdentityDocumentModel.seller_id == seller_id)
            .order_by(m.IdentityDocumentModel.created_at.desc())
        )
        return [map_.to_identity_document(r) for r in rows.scalars().all()]

    async def add_document(self, document: ent.IdentityDocument) -> ent.IdentityDocument:
        self._s.add(
            m.IdentityDocumentModel(
                id=document.id,
                seller_id=document.seller_id,
                document_type=document.document_type,
                file_id=document.file_id,
                status=document.status,
                created_at=document.created_at,
                updated_at=document.created_at,
            )
        )
        await self._s.flush()
        return document

    async def update_document(self, document: ent.IdentityDocument) -> ent.IdentityDocument:
        await self._s.execute(
            update(m.IdentityDocumentModel)
            .where(m.IdentityDocumentModel.id == document.id)
            .values(
                status=document.status,
                ocr_engine=document.ocr_engine,
                ocr_engine_version=document.ocr_engine_version,
                ocr_confidence=document.ocr_confidence,
                ocr_raw=document.ocr_raw,
                extracted_name=document.fields.full_name,
                extracted_cnic_hash=document.extracted_cnic_hash,
                extracted_expiry=document.fields.expiry_date,
                quality_score=document.quality_score,
                rejection_reason=document.rejection_reason,
                processed_at=document.processed_at,
            )
        )
        return document

    async def store_encrypted_fields(
        self, document_id: UUID, *, cnic_encrypted: bytes | None, dob_encrypted: bytes | None
    ) -> None:
        """Write envelope-encrypted PII.

        Separate from `update_document` so encrypted values never travel
        through a domain entity and cannot be logged or serialised by accident.
        """
        await self._s.execute(
            update(m.IdentityDocumentModel)
            .where(m.IdentityDocumentModel.id == document_id)
            .values(
                extracted_cnic_encrypted=cnic_encrypted,
                extracted_dob_encrypted=dob_encrypted,
            )
        )

    async def get_latest_verification(self, seller_id: UUID) -> ent.IdentityVerification | None:
        row = (
            await self._s.execute(
                select(m.IdentityVerificationModel)
                .where(m.IdentityVerificationModel.seller_id == seller_id)
                .order_by(m.IdentityVerificationModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return map_.to_identity_verification(row) if row else None

    async def get_latest_verification_by_id(
        self, verification_id: UUID
    ) -> ent.IdentityVerification | None:
        row = await self._s.get(m.IdentityVerificationModel, verification_id)
        return map_.to_identity_verification(row) if row else None

    async def add_verification(
        self, verification: ent.IdentityVerification
    ) -> ent.IdentityVerification:
        self._s.add(
            m.IdentityVerificationModel(
                id=verification.id,
                seller_id=verification.seller_id,
                decision=verification.decision,
                front_document_id=verification.front_document_id,
                back_document_id=verification.back_document_id,
                selfie_document_id=verification.selfie_document_id,
                created_at=verification.created_at,
                updated_at=verification.created_at,
            )
        )
        await self._s.flush()
        return verification

    async def update_verification(
        self, verification: ent.IdentityVerification
    ) -> ent.IdentityVerification:
        await self._s.execute(
            update(m.IdentityVerificationModel)
            .where(m.IdentityVerificationModel.id == verification.id)
            .values(
                decision=verification.decision,
                face_match_engine=verification.face_match_engine,
                engine_version=verification.engine_version,
                face_similarity=verification.face_similarity,
                face_distance=verification.face_distance,
                threshold_used=verification.threshold_used,
                liveness_passed=verification.liveness_passed,
                name_match_score=verification.name_match_score,
                decision_source=verification.decision_source,
                decided_by=verification.decided_by,
                decision_reason=verification.decision_reason,
                raw_result=verification.raw_result,
                verified_at=verification.verified_at,
            )
        )
        return verification

    async def count_sellers_with_cnic_hash(
        self, cnic_hash: bytes, *, excluding_seller_id: UUID | None = None
    ) -> int:
        """One national ID across many accounts - the classic fraud pattern.

        Indexed on the HMAC, so this is O(log n) and the CNIC itself never
        leaves encrypted storage.
        """
        stmt = select(func.count(func.distinct(m.IdentityDocumentModel.seller_id))).where(
            m.IdentityDocumentModel.extracted_cnic_hash == cnic_hash,
            m.IdentityDocumentModel.deleted_at.is_(None),
        )
        if excluding_seller_id is not None:
            stmt = stmt.where(m.IdentityDocumentModel.seller_id != excluding_seller_id)
        return int((await self._s.execute(stmt)).scalar_one())


class SqlPhoneRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, phone_id: UUID) -> ent.PhoneNumber | None:
        row = await self._s.get(m.PhoneNumberModel, phone_id)
        return map_.to_phone(row) if row and row.deleted_at is None else None

    async def get_primary(self, user_id: UUID) -> ent.PhoneNumber | None:
        row = (
            await self._s.execute(
                _alive(select(m.PhoneNumberModel), m.PhoneNumberModel)
                .where(m.PhoneNumberModel.user_id == user_id)
                .order_by(m.PhoneNumberModel.is_primary.desc(), m.PhoneNumberModel.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        return map_.to_phone(row) if row else None

    async def list_for_user(self, user_id: UUID) -> list[ent.PhoneNumber]:
        rows = await self._s.execute(
            _alive(select(m.PhoneNumberModel), m.PhoneNumberModel).where(
                m.PhoneNumberModel.user_id == user_id
            )
        )
        return [map_.to_phone(r) for r in rows.scalars().all()]

    async def add(self, phone: ent.PhoneNumber) -> ent.PhoneNumber:
        self._s.add(
            m.PhoneNumberModel(
                id=phone.id,
                user_id=phone.user_id,
                e164=phone.e164.value,
                is_primary=phone.is_primary,
                created_at=phone.created_at,
                updated_at=phone.created_at,
            )
        )
        await self._s.flush()
        return phone

    async def update(self, phone: ent.PhoneNumber) -> ent.PhoneNumber:
        await self._s.execute(
            update(m.PhoneNumberModel)
            .where(m.PhoneNumberModel.id == phone.id)
            .values(
                verified_at=phone.verified_at,
                carrier_name=phone.carrier_name,
                line_type=phone.line_type,
                is_disposable=phone.is_disposable,
                country_code=phone.country_code,
                lookup_raw=phone.lookup_raw,
                lookup_at=phone.lookup_at,
            )
        )
        return phone

    async def count_users_with_number(
        self, e164: PhoneE164, *, excluding_user_id: UUID | None = None
    ) -> int:
        stmt = select(func.count(func.distinct(m.PhoneNumberModel.user_id))).where(
            m.PhoneNumberModel.e164 == e164.value, m.PhoneNumberModel.deleted_at.is_(None)
        )
        if excluding_user_id is not None:
            stmt = stmt.where(m.PhoneNumberModel.user_id != excluding_user_id)
        return int((await self._s.execute(stmt)).scalar_one())


class SqlEmailRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_primary(self, user_id: UUID) -> ent.EmailAddress | None:
        row = (
            await self._s.execute(
                _alive(select(m.EmailAddressModel), m.EmailAddressModel)
                .where(m.EmailAddressModel.user_id == user_id)
                .order_by(m.EmailAddressModel.is_primary.desc(), m.EmailAddressModel.created_at)
                .limit(1)
            )
        ).scalar_one_or_none()
        return map_.to_email(row) if row else None

    async def list_for_user(self, user_id: UUID) -> list[ent.EmailAddress]:
        rows = await self._s.execute(
            _alive(select(m.EmailAddressModel), m.EmailAddressModel).where(
                m.EmailAddressModel.user_id == user_id
            )
        )
        return [map_.to_email(r) for r in rows.scalars().all()]

    async def add(self, email: ent.EmailAddress) -> ent.EmailAddress:
        self._s.add(
            m.EmailAddressModel(
                id=email.id,
                user_id=email.user_id,
                email=email.email.value,
                domain=email.email.domain,
                is_primary=email.is_primary,
                verified_at=email.verified_at,
                created_at=email.created_at,
                updated_at=email.created_at,
            )
        )
        await self._s.flush()
        return email

    async def update(self, email: ent.EmailAddress) -> ent.EmailAddress:
        await self._s.execute(
            update(m.EmailAddressModel)
            .where(m.EmailAddressModel.id == email.id)
            .values(
                verified_at=email.verified_at,
                is_disposable=email.is_disposable,
                mx_valid=email.mx_valid,
                domain_age_days=email.domain_age_days,
                lookup_raw=email.lookup_raw,
                lookup_at=email.lookup_at,
            )
        )
        return email


class SqlDeviceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_fingerprint(self, fingerprint_hash: bytes) -> ent.Device | None:
        row = (
            await self._s.execute(
                select(m.DeviceModel).where(m.DeviceModel.fingerprint_hash == fingerprint_hash)
            )
        ).scalar_one_or_none()
        return map_.to_device(row) if row else None

    async def upsert(self, device: ent.Device) -> ent.Device:
        existing = (
            await self._s.execute(
                select(m.DeviceModel).where(
                    m.DeviceModel.fingerprint_hash == device.fingerprint_hash
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.last_seen_at = device.last_seen_at
            return map_.to_device(existing)

        self._s.add(
            m.DeviceModel(
                id=device.id,
                fingerprint_hash=device.fingerprint_hash,
                user_agent=device.user_agent,
                browser=device.browser,
                os=device.os,
                device_type=device.device_type,
                screen_resolution=device.screen_resolution,
                timezone=device.timezone,
                is_bot=device.is_bot,
                is_emulator=device.is_emulator,
                first_seen_at=device.first_seen_at,
                last_seen_at=device.last_seen_at,
            )
        )
        await self._s.flush()
        return device

    async def link(self, link: ent.DeviceLink) -> ent.DeviceLink:
        existing = (
            await self._s.execute(
                select(m.UserDevice).where(
                    m.UserDevice.user_id == link.user_id,
                    m.UserDevice.device_id == link.device_id,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.last_seen_at = link.last_seen_at
            existing.session_count += 1
            return link

        self._s.add(
            m.UserDevice(
                user_id=link.user_id,
                device_id=link.device_id,
                first_seen_at=link.first_seen_at,
                last_seen_at=link.last_seen_at,
            )
        )
        return link

    async def list_for_user(self, user_id: UUID) -> list[ent.Device]:
        rows = await self._s.execute(
            select(m.DeviceModel)
            .join(m.UserDevice, m.UserDevice.device_id == m.DeviceModel.id)
            .where(m.UserDevice.user_id == user_id)
        )
        return [map_.to_device(r) for r in rows.scalars().all()]

    async def count_accounts_sharing_devices(self, user_id: UUID) -> int:
        """Distinct OTHER accounts reachable through this user's devices.

        This single query is the "multiple accounts created from one device"
        detector named in the proposal's problem statement.
        """
        own_devices = select(m.UserDevice.device_id).where(m.UserDevice.user_id == user_id)
        return int(
            (
                await self._s.execute(
                    select(func.count(func.distinct(m.UserDevice.user_id))).where(
                        m.UserDevice.device_id.in_(own_devices),
                        m.UserDevice.user_id != user_id,
                    )
                )
            ).scalar_one()
        )

    async def has_banned_account_on_shared_device(self, user_id: UUID) -> bool:
        own_devices = select(m.UserDevice.device_id).where(m.UserDevice.user_id == user_id)
        count = (
            await self._s.execute(
                select(func.count())
                .select_from(m.UserDevice)
                .join(m.User, m.User.id == m.UserDevice.user_id)
                .where(
                    m.UserDevice.device_id.in_(own_devices),
                    m.UserDevice.user_id != user_id,
                    m.User.status.in_([e.AccountStatus.BANNED, e.AccountStatus.SUSPENDED]),
                )
            )
        ).scalar_one()
        return bool(count)

    async def record_access(self, event: ent.AccessEvent) -> None:
        self._s.add(
            m.AccessEventModel(
                id=event.id,
                user_id=event.user_id,
                device_id=event.device_id,
                ip_address_id=event.ip_address_id,
                ip=event.ip,
                event_type=event.event_type,
                occurred_at=event.occurred_at,
                request_id=event.request_id,
                user_agent=event.user_agent,
            )
        )

    async def list_recent_access(self, user_id: UUID, *, limit: int) -> list[ent.AccessEvent]:
        rows = await self._s.execute(
            select(m.AccessEventModel)
            .where(m.AccessEventModel.user_id == user_id)
            .order_by(m.AccessEventModel.occurred_at.desc())
            .limit(limit)
        )
        return [map_.to_access_event(r) for r in rows.scalars().all()]

    async def get_ip_reputation(self, ip: str) -> ent.IpReputation | None:
        row = (
            await self._s.execute(select(m.IpAddressModel).where(m.IpAddressModel.ip == ip))
        ).scalar_one_or_none()
        return map_.to_ip_reputation(row) if row else None

    async def upsert_ip_reputation(self, reputation: ent.IpReputation) -> ent.IpReputation:
        existing = (
            await self._s.execute(
                select(m.IpAddressModel).where(m.IpAddressModel.ip == reputation.ip)
            )
        ).scalar_one_or_none()
        values = {
            "country_code": reputation.country_code,
            "region": reputation.region,
            "city": reputation.city,
            "asn": reputation.asn,
            "asn_org": reputation.asn_org,
            "is_vpn": reputation.is_vpn,
            "is_proxy": reputation.is_proxy,
            "is_tor": reputation.is_tor,
            "is_datacenter": reputation.is_datacenter,
            "abuse_score": reputation.abuse_score,
            "provider": reputation.provider,
            "lookup_raw": reputation.raw,
            "looked_up_at": reputation.looked_up_at,
        }
        if existing is not None:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            import uuid_utils

            self._s.add(
                m.IpAddressModel(id=UUID(str(uuid_utils.uuid7())), ip=reputation.ip, **values)
            )
        return reputation


#: Comparable listings required before a category median means anything.
#: Below this the median is dominated by the listing being judged, so the
#: price signal reports UNAVAILABLE rather than an unearned pass.
MIN_COMPARABLE_LISTINGS = 5


class SqlListingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, listing_id: UUID) -> ent.Listing | None:
        row = await self._s.get(m.ListingModel, listing_id)
        if row is None or row.deleted_at is not None:
            return None
        analysis = None
        if row.latest_analysis_id:
            analysis_row = await self._s.get(m.ListingAnalysisModel, row.latest_analysis_id)
            analysis = map_.to_listing_analysis(analysis_row) if analysis_row else None
        return map_.to_listing(row, analysis)

    async def list_for_seller(
        self, seller_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[ent.Listing]:
        rows = await self._s.execute(
            _alive(select(m.ListingModel), m.ListingModel)
            .where(m.ListingModel.seller_id == seller_id)
            .order_by(m.ListingModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [map_.to_listing(r) for r in rows.scalars().all()]

    async def count_for_seller(self, seller_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.ListingModel)
                    .where(
                        m.ListingModel.seller_id == seller_id,
                        m.ListingModel.deleted_at.is_(None),
                    )
                )
            ).scalar_one()
        )

    def _public_query_base(
        self,
        *,
        category: str | None,
        q: str | None,
        city: str | None = None,
        area: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        seller_handle: str | None = None,
        attribute_key: str | None = None,
        attribute_value: str | None = None,
        include_sold: bool = False,
        near_latitude: float | None = None,
        near_longitude: float | None = None,
        radius_km: float | None = None,
    ) -> Select[Any]:
        stmt = (
            select(m.ListingModel, m.SellerProfile, m.TrustScoreModel.risk_level)
            .join(m.SellerProfile, m.SellerProfile.id == m.ListingModel.seller_id)
            .outerjoin(
                m.TrustScoreModel, m.TrustScoreModel.id == m.SellerProfile.current_trust_score_id
            )
        ).where(
            # The storefront (MKT-04) also wants a seller's RESERVED/SOLD
            # listings, for their sold-listing history - the anonymous
            # catalog and search never do.
            (
                m.ListingModel.status.in_(
                    [e.ListingStatus.ACTIVE, e.ListingStatus.RESERVED, e.ListingStatus.SOLD]
                )
                if include_sold
                else m.ListingModel.status == e.ListingStatus.ACTIVE
            ),
            m.ListingModel.deleted_at.is_(None),
            m.SellerProfile.deleted_at.is_(None),
        )
        if category is not None:
            stmt = stmt.where(m.ListingModel.category == category)
        if q:
            # The trigram GIN index on `title` (ix_listings_title_trgm) makes
            # this ILIKE cheap even without a leading anchor.
            stmt = stmt.where(m.ListingModel.title.ilike(f"%{q}%"))
        if city:
            stmt = stmt.where(m.ListingModel.city == city)
        if area:
            stmt = stmt.where(m.ListingModel.area == area)
        if min_price is not None:
            stmt = stmt.where(m.ListingModel.price >= min_price)
        if max_price is not None:
            stmt = stmt.where(m.ListingModel.price <= max_price)
        if seller_handle:
            # Powers the public seller storefront (MKT-04) - a seller's own
            # active listings, same PII-free projection as the catalog.
            stmt = stmt.where(m.SellerProfile.handle == seller_handle)
        if attribute_key and attribute_value:
            # MKT-01's attribute search - a JSONB containment check against
            # the freeform {key: value} spec bag (LST-01), not a per-category
            # schema, so this matches whatever a seller actually entered.
            stmt = stmt.where(m.ListingModel.attributes.contains({attribute_key: attribute_value}))
        if near_latitude is not None and near_longitude is not None and radius_km is not None:
            # "Nearby" (MKT-01) / radius search (LOC-01) - a plain Haversine
            # expression against the seller's full-precision coordinates
            # (only the *response* gets rounded, via _approximate_coordinate,
            # not what search filters against). No PostGIS: at this catalog
            # size a function-based filter is simpler to reason about than
            # standing up an extension for one query.
            distance_km = 6371 * func.acos(
                func.cos(func.radians(near_latitude))
                * func.cos(func.radians(m.ListingModel.latitude))
                * func.cos(func.radians(m.ListingModel.longitude) - func.radians(near_longitude))
                + func.sin(func.radians(near_latitude))
                * func.sin(func.radians(m.ListingModel.latitude))
            )
            stmt = stmt.where(m.ListingModel.latitude.isnot(None), distance_km <= radius_km)
        return stmt

    def _order_by(self, stmt: Select[Any], sort: str) -> Select[Any]:
        if sort == "price_asc":
            # NULLS LAST: a listing with no price is not "cheapest".
            return stmt.order_by(m.ListingModel.price.is_(None), m.ListingModel.price.asc())
        if sort == "price_desc":
            return stmt.order_by(m.ListingModel.price.is_(None), m.ListingModel.price.desc())
        return stmt.order_by(m.ListingModel.created_at.desc())

    async def search_public(
        self,
        *,
        category: str | None = None,
        q: str | None = None,
        city: str | None = None,
        area: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        seller_handle: str | None = None,
        attribute_key: str | None = None,
        attribute_value: str | None = None,
        include_sold: bool = False,
        near_latitude: float | None = None,
        near_longitude: float | None = None,
        radius_km: float | None = None,
        sort: str = "newest",
        limit: int = 20,
        offset: int = 0,
    ) -> list[ent.PublicListingSummary]:
        stmt = self._public_query_base(
            category=category,
            q=q,
            city=city,
            area=area,
            min_price=min_price,
            max_price=max_price,
            seller_handle=seller_handle,
            attribute_key=attribute_key,
            attribute_value=attribute_value,
            include_sold=include_sold,
            near_latitude=near_latitude,
            near_longitude=near_longitude,
            radius_km=radius_km,
        )
        stmt = self._order_by(stmt, sort).limit(limit).offset(offset)
        rows = (await self._s.execute(stmt)).all()
        listing_ids = [listing.id for listing, _seller, _risk in rows]
        primary_images = await _primary_image_ids(self._s, listing_ids)

        return [
            _to_public_summary(listing, seller, risk_level, primary_images)
            for listing, seller, risk_level in rows
        ]

    async def count_public(
        self,
        *,
        category: str | None = None,
        q: str | None = None,
        city: str | None = None,
        area: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        seller_handle: str | None = None,
        attribute_key: str | None = None,
        attribute_value: str | None = None,
        include_sold: bool = False,
        near_latitude: float | None = None,
        near_longitude: float | None = None,
        radius_km: float | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(
            self._public_query_base(
                category=category,
                q=q,
                city=city,
                area=area,
                min_price=min_price,
                max_price=max_price,
                seller_handle=seller_handle,
                attribute_key=attribute_key,
                attribute_value=attribute_value,
                include_sold=include_sold,
                near_latitude=near_latitude,
                near_longitude=near_longitude,
                radius_km=radius_km,
            ).subquery()
        )
        return int((await self._s.execute(stmt)).scalar_one())

    async def get_public_detail(self, listing_id: UUID) -> ent.PublicListingDetail | None:
        stmt = (
            select(m.ListingModel, m.SellerProfile, m.TrustScoreModel.risk_level)
            .join(m.SellerProfile, m.SellerProfile.id == m.ListingModel.seller_id)
            .outerjoin(
                m.TrustScoreModel, m.TrustScoreModel.id == m.SellerProfile.current_trust_score_id
            )
            .where(
                m.ListingModel.id == listing_id,
                # A buyer can still open a listing they're mid-deal on (or
                # already bought) via a direct link - not ever from search.
                m.ListingModel.status.in_(
                    [e.ListingStatus.ACTIVE, e.ListingStatus.RESERVED, e.ListingStatus.SOLD]
                ),
                m.ListingModel.deleted_at.is_(None),
                m.SellerProfile.deleted_at.is_(None),
            )
        )
        row = (await self._s.execute(stmt)).first()
        if row is None:
            return None
        listing, seller, risk_level = row

        image_rows = await self._s.execute(
            select(
                m.ListingImageModel.file_id,
                m.ListingImageModel.is_primary,
                m.ListingImageModel.thumbnail_object_key,
            )
            .where(m.ListingImageModel.listing_id == listing_id)
            .order_by(m.ListingImageModel.position)
        )
        images = tuple(
            ent.PublicListingImage(
                file_id=file_id, is_primary=is_primary, thumbnail_object_key=thumb_key
            )
            for file_id, is_primary, thumb_key in image_rows
        )

        return ent.PublicListingDetail(
            id=listing.id,
            title=listing.title,
            description=listing.description,
            price=float(listing.price) if listing.price is not None else None,
            currency=listing.currency,
            category=listing.category,
            condition=listing.condition,
            city=listing.city,
            area=listing.area,
            created_at=listing.created_at,
            seller_id=seller.id,
            seller_handle=seller.handle,
            seller_display_name=seller.display_name,
            status=listing.status.value,
            negotiable=listing.negotiable,
            attributes=dict(listing.attributes or {}),
            video_file_id=listing.video_file_id,
            risk_level=risk_level.value if risk_level is not None else None,
            identity_verified=seller.identity_status == e.VerificationStatus.VERIFIED,
            phone_verified=seller.phone_status == e.VerificationStatus.VERIFIED,
            images=images,
            latitude=_approximate_coordinate(
                float(listing.latitude) if listing.latitude is not None else None
            ),
            longitude=_approximate_coordinate(
                float(listing.longitude) if listing.longitude is not None else None
            ),
        )

    async def add(self, listing: ent.Listing) -> ent.Listing:
        self._s.add(
            m.ListingModel(
                id=listing.id,
                seller_id=listing.seller_id,
                marketplace_id=listing.marketplace_id,
                external_listing_ref=listing.external_listing_ref,
                source=listing.source,
                title=listing.title,
                description=listing.description,
                price=listing.price.amount if listing.price else None,
                currency=listing.price.currency if listing.price else None,
                category=listing.category,
                condition=listing.condition,
                city=listing.city,
                area=listing.area,
                latitude=listing.latitude,
                longitude=listing.longitude,
                country_code=listing.country_code,
                external_url=listing.external_url,
                posted_at=listing.posted_at,
                status=listing.status,
                negotiable=listing.negotiable,
                attributes=listing.attributes,
                video_file_id=listing.video_file_id,
                created_at=listing.created_at,
                updated_at=listing.created_at,
            )
        )
        await self._s.flush()
        return listing

    async def update(self, listing: ent.Listing) -> ent.Listing:
        await self._s.execute(
            update(m.ListingModel)
            .where(m.ListingModel.id == listing.id)
            .values(
                title=listing.title,
                description=listing.description,
                price=listing.price.amount if listing.price else None,
                currency=listing.price.currency if listing.price else None,
                category=listing.category,
                condition=listing.condition,
                # city/area/lat/lng/country_code were silently dropped here
                # before - the column existed, `add()` wrote it, but `update()`
                # never did, so editing a listing's location did nothing.
                city=listing.city,
                area=listing.area,
                latitude=listing.latitude,
                longitude=listing.longitude,
                country_code=listing.country_code,
                status=listing.status,
                negotiable=listing.negotiable,
                attributes=listing.attributes,
                video_file_id=listing.video_file_id,
                latest_analysis_id=(
                    listing.latest_analysis.id if listing.latest_analysis else None
                ),
                version=m.ListingModel.version + 1,
            )
        )
        return listing

    async def add_analysis(self, analysis: ent.ListingAnalysis) -> ent.ListingAnalysis:
        self._s.add(
            m.ListingAnalysisModel(
                id=analysis.id,
                listing_id=analysis.listing_id,
                analyzer_type=analysis.analyzer_type,
                provider=analysis.provider,
                model_name=analysis.model_name,
                model_version=analysis.model_version,
                prompt_version=analysis.prompt_version,
                risk_score=analysis.risk_score,
                confidence=analysis.confidence,
                labels=[dataclasses.asdict(label) for label in analysis.labels],
                findings=analysis.findings,
                price_deviation_pct=analysis.price_deviation_pct,
                raw_response=analysis.raw_response,
                input_tokens=analysis.input_tokens,
                output_tokens=analysis.output_tokens,
                latency_ms=analysis.latency_ms,
                cost_usd=analysis.cost_usd,
                analysed_at=analysis.analysed_at,
            )
        )
        await self._s.execute(
            update(m.ListingModel)
            .where(m.ListingModel.id == analysis.listing_id)
            .values(latest_analysis_id=analysis.id)
        )
        await self._s.flush()
        return analysis

    async def latest_analyses_for_seller(
        self, seller_id: UUID, *, limit: int = 20
    ) -> list[ent.ListingAnalysis]:
        rows = await self._s.execute(
            select(m.ListingAnalysisModel)
            .join(m.ListingModel, m.ListingModel.latest_analysis_id == m.ListingAnalysisModel.id)
            .where(m.ListingModel.seller_id == seller_id, m.ListingModel.deleted_at.is_(None))
            .order_by(m.ListingAnalysisModel.analysed_at.desc())
            .limit(limit)
        )
        return [map_.to_listing_analysis(r) for r in rows.scalars().all()]

    async def category_median_price(self, category: str, *, currency: str) -> float | None:
        """Median, not mean: a single absurd listing must not move the baseline
        that "too good to be true" is measured against.

        Returns None below MIN_COMPARABLE_LISTINGS, and that is the important
        part. With one listing in a category the median *is* that listing, so
        its deviation is 0% and the signal reports "prices are in line with
        similar items" - a PASS awarded on no evidence at all. Returning None
        makes the signal UNAVAILABLE instead, which the scoring policy excludes
        from the denominator rather than scoring as a pass.
        """
        row = (
            await self._s.execute(
                select(
                    func.percentile_cont(0.5).within_group(m.ListingModel.price.asc()),
                    func.count(m.ListingModel.id),
                ).where(
                    m.ListingModel.category == category,
                    m.ListingModel.currency == currency,
                    m.ListingModel.price.isnot(None),
                    m.ListingModel.deleted_at.is_(None),
                )
            )
        ).one_or_none()

        if row is None:
            return None
        median, comparable = row
        if median is None or comparable < MIN_COMPARABLE_LISTINGS:
            return None
        return float(median)

    async def create_image(self, image: ent.ListingImage) -> ent.ListingImage:
        """Persist a listing image row.

        The perceptual_hash column is populated by the caller, not here:
        the repository layer should not depend on imagehash (that is an
        adapter concern), and the hash may legitimately be None if the
        image format cannot be decoded.
        """
        self._s.add(
            m.ListingImageModel(
                id=image.id,
                listing_id=image.listing_id,
                file_id=image.file_id,
                position=image.position,
                width=image.width,
                height=image.height,
                perceptual_hash=image.perceptual_hash,
                sha256=image.sha256,
                is_primary=image.is_primary,
                created_at=image.created_at,
            )
        )
        await self._s.flush()
        return image

    async def list_images(self, listing_id: UUID) -> list[ent.ListingImage]:
        rows = await self._s.execute(
            select(m.ListingImageModel)
            .where(m.ListingImageModel.listing_id == listing_id)
            .order_by(m.ListingImageModel.position)
        )
        return [map_.to_listing_image(r) for r in rows.scalars().all()]

    async def count_images(self, listing_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count(m.ListingImageModel.id)).where(
                        m.ListingImageModel.listing_id == listing_id
                    )
                )
            ).scalar_one()
        )

    async def find_near_duplicate_hash(
        self,
        phash: bytes,
        *,
        seller_id: UUID,
        hamming_threshold: int = 5,
        exclude_image_id: UUID | None = None,
    ) -> ent.ListingImage | None:
        """Return the first existing image with a Hamming distance <= threshold.

        Done in Python after a seller-scoped fetch because PostgreSQL does not
        have a native bit-distance aggregate without pg_trgm or a custom
        extension. The number of images per seller is small enough that this
        is fine.
        """
        stmt = (
            select(m.ListingImageModel)
            .join(m.ListingModel, m.ListingModel.id == m.ListingImageModel.listing_id)
            .where(
                m.ListingModel.seller_id == seller_id,
                m.ListingModel.deleted_at.is_(None),
                m.ListingImageModel.perceptual_hash.isnot(None),
            )
        )
        if exclude_image_id is not None:
            stmt = stmt.where(m.ListingImageModel.id != exclude_image_id)
        rows = (await self._s.execute(stmt)).scalars().all()
        for row in rows:
            if row.perceptual_hash is None:
                continue
            # XOR then popcount — Hamming distance on packed bytes
            xor = int.from_bytes(phash, "big") ^ int.from_bytes(row.perceptual_hash, "big")
            distance = bin(xor).count("1")
            if distance <= hamming_threshold:
                return map_.to_listing_image(row)
        return None


def _approximate_coordinate(value: float | None) -> float | None:
    """Round a public-facing coordinate to ~1.1km precision (LOC-01).

    `PublicListingSummary`/`PublicListingDetail` are the buyer-facing
    projections - unlike the seller's own `Listing` entity, which keeps full
    precision for editing, these must never carry an exact, dox-able
    coordinate. Two decimal places is the "approximate area" the product
    promises rather than a street address, without needing the full
    province/city/area/radius/centroid model (LOC-01's larger redesign) to
    be built first.
    """
    return round(value, 2) if value is not None else None


async def _primary_image_ids(
    session: AsyncSession, listing_ids: list[UUID]
) -> dict[UUID, tuple[UUID, str | None]]:
    """Shared by the public catalog and favorites reads - both project a
    listing down to its primary image (and that image's thumbnail, if one
    was generated) in one batched query rather than one per row."""
    if not listing_ids:
        return {}
    rows = await session.execute(
        select(
            m.ListingImageModel.listing_id,
            m.ListingImageModel.file_id,
            m.ListingImageModel.thumbnail_object_key,
        ).where(
            m.ListingImageModel.listing_id.in_(listing_ids),
            m.ListingImageModel.is_primary.is_(True),
        )
    )
    return {listing_id: (file_id, thumb_key) for listing_id, file_id, thumb_key in rows}


def _to_public_summary(
    listing: m.ListingModel,
    seller: m.SellerProfile,
    risk_level: e.RiskLevel | None,
    primary_images: dict[UUID, tuple[UUID, str | None]],
) -> ent.PublicListingSummary:
    image = primary_images.get(listing.id)
    return ent.PublicListingSummary(
        id=listing.id,
        title=listing.title,
        price=float(listing.price) if listing.price is not None else None,
        currency=listing.currency,
        category=listing.category,
        condition=listing.condition,
        city=listing.city,
        area=listing.area,
        created_at=listing.created_at,
        seller_id=seller.id,
        seller_handle=seller.handle,
        seller_display_name=seller.display_name,
        status=listing.status.value,
        negotiable=listing.negotiable,
        risk_level=risk_level.value if risk_level is not None else None,
        identity_verified=seller.identity_status == e.VerificationStatus.VERIFIED,
        phone_verified=seller.phone_status == e.VerificationStatus.VERIFIED,
        primary_image_file_id=image[0] if image else None,
        primary_image_thumbnail_key=image[1] if image else None,
        latitude=_approximate_coordinate(
            float(listing.latitude) if listing.latitude is not None else None
        ),
        longitude=_approximate_coordinate(
            float(listing.longitude) if listing.longitude is not None else None
        ),
    )


class SqlFavoriteRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, favorite: ent.Favorite) -> ent.Favorite:
        self._s.add(
            m.FavoriteModel(
                id=favorite.id,
                user_id=favorite.user_id,
                listing_id=favorite.listing_id,
                created_at=favorite.created_at,
            )
        )
        await self._s.flush()
        return favorite

    async def remove(self, *, user_id: UUID, listing_id: UUID) -> None:
        await self._s.execute(
            delete(m.FavoriteModel).where(
                m.FavoriteModel.user_id == user_id, m.FavoriteModel.listing_id == listing_id
            )
        )

    async def exists(self, *, user_id: UUID, listing_id: UUID) -> bool:
        row = (
            await self._s.execute(
                select(m.FavoriteModel.id).where(
                    m.FavoriteModel.user_id == user_id, m.FavoriteModel.listing_id == listing_id
                )
            )
        ).first()
        return row is not None

    async def list_ids_for_user(self, user_id: UUID) -> frozenset[UUID]:
        rows = await self._s.execute(
            select(m.FavoriteModel.listing_id).where(m.FavoriteModel.user_id == user_id)
        )
        return frozenset(rows.scalars().all())

    async def list_favorite_listings(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[ent.PublicListingSummary]:
        stmt = (
            select(
                m.ListingModel,
                m.SellerProfile,
                m.FavoriteModel.created_at,
                m.TrustScoreModel.risk_level,
            )
            .join(m.FavoriteModel, m.FavoriteModel.listing_id == m.ListingModel.id)
            .join(m.SellerProfile, m.SellerProfile.id == m.ListingModel.seller_id)
            .outerjoin(
                m.TrustScoreModel, m.TrustScoreModel.id == m.SellerProfile.current_trust_score_id
            )
            .where(
                m.FavoriteModel.user_id == user_id,
                m.ListingModel.deleted_at.is_(None),
                m.SellerProfile.deleted_at.is_(None),
            )
            .order_by(m.FavoriteModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).all()
        listing_ids = [listing.id for listing, _seller, _favorited_at, _risk in rows]
        primary_images = await _primary_image_ids(self._s, listing_ids)

        return [
            _to_public_summary(listing, seller, risk_level, primary_images)
            for listing, seller, _favorited_at, risk_level in rows
        ]

    async def count_for_user(self, user_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.FavoriteModel)
                    .where(m.FavoriteModel.user_id == user_id)
                )
            ).scalar_one()
        )


def _to_saved_search(row: m.SavedSearchModel) -> ent.SavedSearch:
    return ent.SavedSearch(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        category=row.category,
        q=row.q,
        city=row.city,
        area=row.area,
        min_price=float(row.min_price) if row.min_price is not None else None,
        max_price=float(row.max_price) if row.max_price is not None else None,
        created_at=row.created_at,
    )


class SqlSavedSearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, search: ent.SavedSearch) -> ent.SavedSearch:
        self._s.add(
            m.SavedSearchModel(
                id=search.id,
                user_id=search.user_id,
                name=search.name,
                category=search.category,
                q=search.q,
                city=search.city,
                area=search.area,
                min_price=search.min_price,
                max_price=search.max_price,
            )
        )
        await self._s.flush()
        return search

    async def list_for_user(self, user_id: UUID) -> list[ent.SavedSearch]:
        stmt = (
            select(m.SavedSearchModel)
            .where(m.SavedSearchModel.user_id == user_id)
            .order_by(m.SavedSearchModel.created_at.desc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_saved_search(row) for row in rows]

    async def count_for_user(self, user_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.SavedSearchModel)
                    .where(m.SavedSearchModel.user_id == user_id)
                )
            ).scalar_one()
        )

    async def get(self, search_id: UUID) -> ent.SavedSearch | None:
        row = await self._s.get(m.SavedSearchModel, search_id)
        return _to_saved_search(row) if row else None

    async def remove(self, *, user_id: UUID, search_id: UUID) -> None:
        await self._s.execute(
            delete(m.SavedSearchModel).where(
                m.SavedSearchModel.id == search_id, m.SavedSearchModel.user_id == user_id
            )
        )


def _to_conversation(row: m.ConversationModel) -> ent.Conversation:
    return ent.Conversation(
        id=row.id,
        seller_id=row.seller_id,
        buyer_id=row.buyer_id,
        created_at=row.created_at,
        last_message_at=row.last_message_at,
        listing_id=row.listing_id,
        listing_title=row.listing_title_snapshot,
        listing_price=float(row.listing_price_snapshot)
        if row.listing_price_snapshot is not None
        else None,
        listing_currency=row.listing_currency_snapshot,
        muted_by_buyer=row.muted_by_buyer,
        muted_by_seller=row.muted_by_seller,
    )


def _to_message(row: m.MessageModel) -> ent.Message:
    return ent.Message(
        id=row.id,
        conversation_id=row.conversation_id,
        sender_id=row.sender_id,
        body=row.body,
        created_at=row.created_at,
        read_at=row.read_at,
    )


class SqlMessagingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_conversation(self, conversation_id: UUID) -> ent.Conversation | None:
        row = await self._s.get(m.ConversationModel, conversation_id)
        return _to_conversation(row) if row else None

    async def find_conversation(
        self, *, buyer_id: UUID, seller_id: UUID, listing_id: UUID | None
    ) -> ent.Conversation | None:
        stmt = select(m.ConversationModel).where(
            m.ConversationModel.buyer_id == buyer_id,
            m.ConversationModel.seller_id == seller_id,
        )
        # IS NOT DISTINCT FROM, not `==`: a plain `listing_id == None` compiles
        # to `= NULL`, which never matches in SQL - the general listing-less
        # thread would be re-created on every message.
        stmt = stmt.where(m.ConversationModel.listing_id.is_not_distinct_from(listing_id))
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return _to_conversation(row) if row else None

    async def create_conversation(self, conversation: ent.Conversation) -> ent.Conversation:
        self._s.add(
            m.ConversationModel(
                id=conversation.id,
                listing_id=conversation.listing_id,
                seller_id=conversation.seller_id,
                buyer_id=conversation.buyer_id,
                created_at=conversation.created_at,
                last_message_at=conversation.last_message_at,
                listing_title_snapshot=conversation.listing_title,
                listing_price_snapshot=conversation.listing_price,
                listing_currency_snapshot=conversation.listing_currency,
            )
        )
        await self._s.flush()
        return conversation

    async def touch_conversation(self, conversation_id: UUID, *, at: datetime) -> None:
        await self._s.execute(
            update(m.ConversationModel)
            .where(m.ConversationModel.id == conversation_id)
            .values(last_message_at=at)
        )

    async def set_muted(self, conversation_id: UUID, *, user_id: UUID, muted: bool) -> None:
        participants = await self.get_participants(conversation_id)
        if participants is None:
            return
        buyer_user_id, _seller_user_id = participants
        stmt = update(m.ConversationModel).where(m.ConversationModel.id == conversation_id)
        stmt = (
            stmt.values(muted_by_buyer=muted)
            if user_id == buyer_user_id
            else stmt.values(muted_by_seller=muted)
        )
        await self._s.execute(stmt)

    async def get_participants(self, conversation_id: UUID) -> tuple[UUID, UUID] | None:
        row = (
            await self._s.execute(
                select(m.ConversationModel.buyer_id, m.SellerProfile.user_id)
                .join(m.SellerProfile, m.SellerProfile.id == m.ConversationModel.seller_id)
                .where(m.ConversationModel.id == conversation_id)
            )
        ).first()
        return (row.buyer_id, row.user_id) if row else None

    async def list_conversations_for_user(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[ent.ConversationSummary]:
        stmt = (
            select(m.ConversationModel, m.SellerProfile, m.User, m.ListingModel)
            .join(m.SellerProfile, m.SellerProfile.id == m.ConversationModel.seller_id)
            .join(m.User, m.User.id == m.ConversationModel.buyer_id)
            .outerjoin(m.ListingModel, m.ListingModel.id == m.ConversationModel.listing_id)
            .where((m.ConversationModel.buyer_id == user_id) | (m.SellerProfile.user_id == user_id))
            .order_by(m.ConversationModel.last_message_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).all()
        conversation_ids = [c.id for c, _seller, _buyer, _listing in rows]
        previews = await self._previews(conversation_ids)
        unread = await self._unread_counts(conversation_ids, reader_id=user_id)

        summaries = []
        for conversation, seller, buyer, listing in rows:
            is_seller_side = seller.user_id == user_id
            entity = _to_conversation(conversation)
            summaries.append(
                ent.ConversationSummary(
                    conversation=entity,
                    counterpart_name=seller.display_name if not is_seller_side else buyer.full_name,
                    counterpart_user_id=seller.user_id if not is_seller_side else buyer.id,
                    # The snapshot taken at creation, not the live listing -
                    # falls back to the live title only for conversations
                    # that predate the snapshot column (SOC-01).
                    listing_title=entity.listing_title
                    or (listing.title if listing is not None else None),
                    last_message_preview=previews.get(conversation.id),
                    unread_count=unread.get(conversation.id, 0),
                    muted=entity.muted_by_seller if is_seller_side else entity.muted_by_buyer,
                )
            )
        return summaries

    async def _previews(self, conversation_ids: list[UUID]) -> dict[UUID, str]:
        if not conversation_ids:
            return {}
        # DISTINCT ON: the latest message body per conversation, in one
        # query rather than one per row - Postgres-specific, matching the
        # rest of this module's use of native features.
        stmt = (
            select(m.MessageModel.conversation_id, m.MessageModel.body)
            .where(m.MessageModel.conversation_id.in_(conversation_ids))
            .order_by(m.MessageModel.conversation_id, m.MessageModel.created_at.desc())
            .distinct(m.MessageModel.conversation_id)
        )
        rows = await self._s.execute(stmt)
        # `dict(rows.tuples())` is broken: `Result` exposes `.keys()` (the
        # column names), so the dict constructor mistakes it for a mapping
        # and does `rows[key]`, which `Result` doesn't support - `.all()`
        # materialises to a plain list first, which has no `.keys()` to
        # trip that fast path.
        return dict(rows.tuples().all())

    async def _unread_counts(
        self, conversation_ids: list[UUID], *, reader_id: UUID
    ) -> dict[UUID, int]:
        if not conversation_ids:
            return {}
        stmt = (
            select(m.MessageModel.conversation_id, func.count())
            .where(
                m.MessageModel.conversation_id.in_(conversation_ids),
                m.MessageModel.sender_id != reader_id,
                m.MessageModel.read_at.is_(None),
            )
            .group_by(m.MessageModel.conversation_id)
        )
        rows = await self._s.execute(stmt)
        return dict(rows.tuples().all())

    async def count_conversations_for_user(self, user_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(m.ConversationModel)
            .join(m.SellerProfile, m.SellerProfile.id == m.ConversationModel.seller_id)
            .where((m.ConversationModel.buyer_id == user_id) | (m.SellerProfile.user_id == user_id))
        )
        return int((await self._s.execute(stmt)).scalar_one())

    async def add_message(self, message: ent.Message) -> ent.Message:
        self._s.add(
            m.MessageModel(
                id=message.id,
                conversation_id=message.conversation_id,
                sender_id=message.sender_id,
                body=message.body,
                created_at=message.created_at,
                read_at=message.read_at,
            )
        )
        await self._s.flush()
        return message

    async def list_messages(
        self, conversation_id: UUID, *, limit: int = 50, offset: int = 0
    ) -> list[ent.Message]:
        stmt = (
            select(m.MessageModel)
            .where(m.MessageModel.conversation_id == conversation_id)
            .order_by(m.MessageModel.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [_to_message(r) for r in rows]

    async def mark_read(self, conversation_id: UUID, *, reader_id: UUID, at: datetime) -> None:
        await self._s.execute(
            update(m.MessageModel)
            .where(
                m.MessageModel.conversation_id == conversation_id,
                m.MessageModel.sender_id != reader_id,
                m.MessageModel.read_at.is_(None),
            )
            .values(read_at=at)
        )


class SqlReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, report: ent.Report) -> ent.Report:
        self._s.add(
            m.ReportModel(
                id=report.id,
                reporter_id=report.reporter_id,
                target_type=report.target_type,
                target_id=report.target_id,
                category=report.category,
                description=report.description,
                status=report.status,
                created_at=report.created_at,
            )
        )
        await self._s.flush()
        return report

    async def get(self, report_id: UUID) -> ent.Report | None:
        row = await self._s.get(m.ReportModel, report_id)
        return map_.to_report(row) if row else None

    async def list_for_reporter(self, reporter_id: UUID, *, limit: int = 50) -> list[ent.Report]:
        stmt = (
            select(m.ReportModel)
            .where(m.ReportModel.reporter_id == reporter_id)
            .order_by(m.ReportModel.created_at.desc())
            .limit(limit)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_report(r) for r in rows]

    async def list_queue(
        self, *, status: e.ReportStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[ent.Report]:
        stmt = select(m.ReportModel).order_by(m.ReportModel.created_at.desc())
        if status is not None:
            stmt = stmt.where(m.ReportModel.status == status)
        stmt = stmt.limit(limit).offset(offset)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_report(r) for r in rows]

    async def count_queue(self, *, status: e.ReportStatus | None = None) -> int:
        stmt = select(func.count()).select_from(m.ReportModel)
        if status is not None:
            stmt = stmt.where(m.ReportModel.status == status)
        return int((await self._s.execute(stmt)).scalar_one())

    async def resolve(
        self,
        report_id: UUID,
        *,
        status: e.ReportStatus,
        resolution_note: str | None,
        resolved_by: UUID,
        resolved_at: datetime,
    ) -> ent.Report:
        await self._s.execute(
            update(m.ReportModel)
            .where(m.ReportModel.id == report_id)
            .values(
                status=status,
                resolution_note=resolution_note,
                resolved_by=resolved_by,
                resolved_at=resolved_at,
            )
        )
        row = await self._s.get(m.ReportModel, report_id)
        assert row is not None
        return map_.to_report(row)


class SqlBlockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, block: ent.Block) -> ent.Block:
        self._s.add(
            m.BlockModel(
                id=block.id,
                blocker_id=block.blocker_id,
                blocked_id=block.blocked_id,
                created_at=block.created_at,
            )
        )
        await self._s.flush()
        return block

    async def remove(self, *, blocker_id: UUID, blocked_id: UUID) -> None:
        await self._s.execute(
            delete(m.BlockModel).where(
                m.BlockModel.blocker_id == blocker_id, m.BlockModel.blocked_id == blocked_id
            )
        )

    async def exists(self, *, blocker_id: UUID, blocked_id: UUID) -> bool:
        row = (
            await self._s.execute(
                select(m.BlockModel.id).where(
                    m.BlockModel.blocker_id == blocker_id, m.BlockModel.blocked_id == blocked_id
                )
            )
        ).first()
        return row is not None

    async def is_blocked_either_way(self, user_a: UUID, user_b: UUID) -> bool:
        row = (
            await self._s.execute(
                select(m.BlockModel.id).where(
                    or_(
                        and_(m.BlockModel.blocker_id == user_a, m.BlockModel.blocked_id == user_b),
                        and_(m.BlockModel.blocker_id == user_b, m.BlockModel.blocked_id == user_a),
                    )
                )
            )
        ).first()
        return row is not None

    async def list_blocked_ids(self, blocker_id: UUID) -> frozenset[UUID]:
        rows = await self._s.execute(
            select(m.BlockModel.blocked_id).where(m.BlockModel.blocker_id == blocker_id)
        )
        return frozenset(rows.scalars().all())


class SqlOfferRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, offer: ent.Offer) -> ent.Offer:
        self._s.add(
            m.OfferModel(
                id=offer.id,
                conversation_id=offer.conversation_id,
                listing_id=offer.listing_id,
                buyer_id=offer.buyer_id,
                seller_id=offer.seller_id,
                offered_by=offer.offered_by,
                amount=offer.amount,
                currency=offer.currency,
                status=offer.status,
                created_at=offer.created_at,
                expires_at=offer.expires_at,
                message=offer.message,
                parent_offer_id=offer.parent_offer_id,
            )
        )
        await self._s.flush()
        return offer

    async def get(self, offer_id: UUID) -> ent.Offer | None:
        row = await self._s.get(m.OfferModel, offer_id)
        return map_.to_offer(row) if row else None

    async def list_for_conversation(self, conversation_id: UUID) -> list[ent.Offer]:
        stmt = (
            select(m.OfferModel)
            .where(m.OfferModel.conversation_id == conversation_id)
            .order_by(m.OfferModel.created_at.asc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_offer(r) for r in rows]

    async def get_open_for_listing(self, listing_id: UUID) -> ent.Offer | None:
        stmt = select(m.OfferModel).where(
            m.OfferModel.listing_id == listing_id, m.OfferModel.status == e.OfferStatus.PENDING
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_offer(row) if row else None

    async def close(
        self, offer_id: UUID, *, status: e.OfferStatus, responded_at: datetime
    ) -> ent.Offer:
        await self._s.execute(
            update(m.OfferModel)
            .where(m.OfferModel.id == offer_id)
            .values(status=status, responded_at=responded_at)
        )
        row = await self._s.get(m.OfferModel, offer_id)
        assert row is not None
        return map_.to_offer(row)


class SqlTransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, transaction: ent.Transaction) -> ent.Transaction:
        self._s.add(
            m.TransactionModel(
                id=transaction.id,
                listing_id=transaction.listing_id,
                buyer_id=transaction.buyer_id,
                seller_id=transaction.seller_id,
                offer_id=transaction.offer_id,
                amount=transaction.amount,
                currency=transaction.currency,
                status=transaction.status,
                created_at=transaction.created_at,
            )
        )
        await self._s.flush()
        return transaction

    async def get(self, transaction_id: UUID) -> ent.Transaction | None:
        row = await self._s.get(m.TransactionModel, transaction_id)
        return map_.to_transaction(row) if row else None

    async def get_open_for_listing(self, listing_id: UUID) -> ent.Transaction | None:
        stmt = select(m.TransactionModel).where(
            m.TransactionModel.listing_id == listing_id,
            m.TransactionModel.status.notin_(
                [e.TransactionStatus.COMPLETED, e.TransactionStatus.CANCELLED]
            ),
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_transaction(row) if row else None

    async def list_for_user(
        self, user_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[ent.Transaction]:
        stmt = (
            select(m.TransactionModel)
            .where(
                or_(
                    m.TransactionModel.buyer_id == user_id,
                    m.TransactionModel.seller_id == user_id,
                )
            )
            .order_by(m.TransactionModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_transaction(r) for r in rows]

    async def update_status(
        self,
        transaction_id: UUID,
        *,
        status: e.TransactionStatus,
        at: datetime,
        cancel_reason: str | None = None,
    ) -> ent.Transaction:
        values: dict[str, Any] = {"status": status, "updated_at": at}
        if status == e.TransactionStatus.COMPLETED:
            values["completed_at"] = at
        if status == e.TransactionStatus.CANCELLED:
            values["cancelled_at"] = at
            values["cancel_reason"] = cancel_reason
        await self._s.execute(
            update(m.TransactionModel)
            .where(m.TransactionModel.id == transaction_id)
            .values(**values)
        )
        row = await self._s.get(m.TransactionModel, transaction_id)
        assert row is not None
        return map_.to_transaction(row)


class SqlInstallmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add_plan(self, plan: ent.InstallmentPlan) -> ent.InstallmentPlan:
        self._s.add(
            m.InstallmentPlanModel(
                id=plan.id,
                transaction_id=plan.transaction_id,
                buyer_id=plan.buyer_id,
                seller_id=plan.seller_id,
                total_amount=plan.total_amount,
                currency=plan.currency,
                installment_count=plan.installment_count,
                status=plan.status,
                created_at=plan.created_at,
            )
        )
        await self._s.flush()
        return plan

    async def get_plan(self, plan_id: UUID) -> ent.InstallmentPlan | None:
        row = await self._s.get(m.InstallmentPlanModel, plan_id)
        return map_.to_installment_plan(row) if row else None

    async def get_plan_for_transaction(self, transaction_id: UUID) -> ent.InstallmentPlan | None:
        stmt = (
            select(m.InstallmentPlanModel)
            .where(m.InstallmentPlanModel.transaction_id == transaction_id)
            .order_by(m.InstallmentPlanModel.created_at.desc())
            .limit(1)
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_installment_plan(row) if row else None

    async def update_plan(self, plan: ent.InstallmentPlan) -> ent.InstallmentPlan:
        await self._s.execute(
            update(m.InstallmentPlanModel)
            .where(m.InstallmentPlanModel.id == plan.id)
            .values(status=plan.status, cancelled_at=plan.cancelled_at)
        )
        return plan

    async def add_installment(self, installment: ent.Installment) -> ent.Installment:
        self._s.add(
            m.InstallmentModel(
                id=installment.id,
                plan_id=installment.plan_id,
                sequence_number=installment.sequence_number,
                amount=installment.amount,
                due_at=installment.due_at,
                status=installment.status,
                created_at=installment.created_at,
            )
        )
        await self._s.flush()
        return installment

    async def list_installments(self, plan_id: UUID) -> list[ent.Installment]:
        stmt = (
            select(m.InstallmentModel)
            .where(m.InstallmentModel.plan_id == plan_id)
            .order_by(m.InstallmentModel.sequence_number.asc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_installment(r) for r in rows]

    async def get_installment(self, installment_id: UUID) -> ent.Installment | None:
        row = await self._s.get(m.InstallmentModel, installment_id)
        return map_.to_installment(row) if row else None

    async def update_installment(self, installment: ent.Installment) -> ent.Installment:
        await self._s.execute(
            update(m.InstallmentModel)
            .where(m.InstallmentModel.id == installment.id)
            .values(
                status=installment.status,
                paid_at=installment.paid_at,
                paid_by=installment.paid_by,
            )
        )
        return installment


class SqlAuctionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, auction: ent.Auction) -> ent.Auction:
        self._s.add(
            m.AuctionModel(
                id=auction.id,
                listing_id=auction.listing_id,
                seller_id=auction.seller_id,
                starting_price=auction.starting_price,
                currency=auction.currency,
                ends_at=auction.ends_at,
                status=auction.status,
                created_at=auction.created_at,
                reserve_price=auction.reserve_price,
            )
        )
        await self._s.flush()
        return auction

    async def get(self, auction_id: UUID) -> ent.Auction | None:
        row = await self._s.get(m.AuctionModel, auction_id)
        return map_.to_auction(row) if row else None

    async def get_for_listing(self, listing_id: UUID) -> ent.Auction | None:
        stmt = (
            select(m.AuctionModel)
            .where(m.AuctionModel.listing_id == listing_id)
            .order_by(m.AuctionModel.created_at.desc())
            .limit(1)
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_auction(row) if row else None

    async def update(self, auction: ent.Auction) -> ent.Auction:
        await self._s.execute(
            update(m.AuctionModel)
            .where(m.AuctionModel.id == auction.id)
            .values(
                status=auction.status,
                winning_bid_id=auction.winning_bid_id,
                ended_at=auction.ended_at,
            )
        )
        return auction

    async def list_ending_before(self, at: datetime, *, limit: int = 100) -> list[ent.Auction]:
        stmt = (
            select(m.AuctionModel)
            .where(
                m.AuctionModel.status == e.AuctionStatus.ACTIVE,
                m.AuctionModel.ends_at <= at,
            )
            .limit(limit)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_auction(r) for r in rows]

    async def add_bid(self, bid: ent.Bid) -> ent.Bid:
        self._s.add(
            m.BidModel(
                id=bid.id,
                auction_id=bid.auction_id,
                bidder_id=bid.bidder_id,
                amount=bid.amount,
                created_at=bid.created_at,
            )
        )
        await self._s.flush()
        return bid

    async def list_bids(self, auction_id: UUID) -> list[ent.Bid]:
        stmt = (
            select(m.BidModel)
            .where(m.BidModel.auction_id == auction_id)
            .order_by(m.BidModel.amount.desc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_bid(r) for r in rows]

    async def get_highest_bid(self, auction_id: UUID) -> ent.Bid | None:
        stmt = (
            select(m.BidModel)
            .where(m.BidModel.auction_id == auction_id)
            .order_by(m.BidModel.amount.desc())
            .limit(1)
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_bid(row) if row else None


class SqlMeetingVenueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, venue: ent.MeetingVenue) -> ent.MeetingVenue:
        self._s.add(
            m.MeetingVenueModel(
                id=venue.id,
                name=venue.name,
                address=venue.address,
                city=venue.city,
                area=venue.area,
                latitude=venue.latitude,
                longitude=venue.longitude,
                is_active=venue.is_active,
                notes=venue.notes,
                created_at=venue.created_at,
            )
        )
        await self._s.flush()
        return venue

    async def get(self, venue_id: UUID) -> ent.MeetingVenue | None:
        row = await self._s.get(m.MeetingVenueModel, venue_id)
        return map_.to_meeting_venue(row) if row else None

    async def list_near(self, *, city: str, limit: int = 5) -> list[ent.MeetingVenue]:
        stmt = (
            select(m.MeetingVenueModel)
            .where(
                m.MeetingVenueModel.city == city,
                m.MeetingVenueModel.is_active.is_(True),
            )
            .order_by(m.MeetingVenueModel.created_at.desc())
            .limit(limit)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_meeting_venue(r) for r in rows]

    async def list_all(self, *, limit: int = 50, offset: int = 0) -> list[ent.MeetingVenue]:
        stmt = (
            select(m.MeetingVenueModel)
            .order_by(m.MeetingVenueModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_meeting_venue(r) for r in rows]

    async def set_active(self, venue_id: UUID, *, is_active: bool) -> ent.MeetingVenue:
        await self._s.execute(
            update(m.MeetingVenueModel)
            .where(m.MeetingVenueModel.id == venue_id)
            .values(is_active=is_active)
        )
        row = await self._s.get(m.MeetingVenueModel, venue_id)
        assert row is not None
        return map_.to_meeting_venue(row)


class SqlMeetupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, meetup: ent.Meetup) -> ent.Meetup:
        self._s.add(
            m.MeetupModel(
                id=meetup.id,
                conversation_id=meetup.conversation_id,
                listing_id=meetup.listing_id,
                buyer_id=meetup.buyer_id,
                seller_id=meetup.seller_id,
                proposed_by=meetup.proposed_by,
                venue_id=meetup.venue_id,
                proposed_time=meetup.proposed_time,
                status=meetup.status,
                created_at=meetup.created_at,
                message=meetup.message,
            )
        )
        await self._s.flush()
        return meetup

    async def get(self, meetup_id: UUID) -> ent.Meetup | None:
        row = await self._s.get(m.MeetupModel, meetup_id)
        return map_.to_meetup(row) if row else None

    async def list_for_conversation(self, conversation_id: UUID) -> list[ent.Meetup]:
        stmt = (
            select(m.MeetupModel)
            .where(m.MeetupModel.conversation_id == conversation_id)
            .order_by(m.MeetupModel.created_at.asc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_meetup(r) for r in rows]

    async def get_open_for_conversation(self, conversation_id: UUID) -> ent.Meetup | None:
        stmt = select(m.MeetupModel).where(
            m.MeetupModel.conversation_id == conversation_id,
            m.MeetupModel.status == e.MeetupStatus.PROPOSED,
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_meetup(row) if row else None

    async def close(
        self, meetup_id: UUID, *, status: e.MeetupStatus, responded_at: datetime
    ) -> ent.Meetup:
        await self._s.execute(
            update(m.MeetupModel)
            .where(m.MeetupModel.id == meetup_id)
            .values(status=status, responded_at=responded_at)
        )
        row = await self._s.get(m.MeetupModel, meetup_id)
        assert row is not None
        return map_.to_meetup(row)


class SqlFollowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, follow: ent.Follow) -> ent.Follow:
        self._s.add(
            m.FollowModel(
                id=follow.id,
                follower_id=follow.follower_id,
                seller_id=follow.seller_id,
                created_at=follow.created_at,
            )
        )
        await self._s.flush()
        return follow

    async def remove(self, *, follower_id: UUID, seller_id: UUID) -> None:
        await self._s.execute(
            delete(m.FollowModel).where(
                m.FollowModel.follower_id == follower_id, m.FollowModel.seller_id == seller_id
            )
        )

    async def exists(self, *, follower_id: UUID, seller_id: UUID) -> bool:
        row = (
            await self._s.execute(
                select(m.FollowModel.id).where(
                    m.FollowModel.follower_id == follower_id,
                    m.FollowModel.seller_id == seller_id,
                )
            )
        ).first()
        return row is not None

    async def list_followed_seller_ids(self, follower_id: UUID) -> frozenset[UUID]:
        rows = await self._s.execute(
            select(m.FollowModel.seller_id).where(m.FollowModel.follower_id == follower_id)
        )
        return frozenset(rows.scalars().all())

    async def count_followers(self, seller_id: UUID) -> int:
        result = await self._s.execute(
            select(func.count(m.FollowModel.id)).where(m.FollowModel.seller_id == seller_id)
        )
        return int(result.scalar_one())


class SqlReviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    @staticmethod
    def _counterpart_exists() -> Any:
        """The blind-reveal rule as a correlated subquery: a review is
        visible once a row exists for the same transaction with reviewer
        and reviewee swapped."""
        counterpart = aliased(m.ReviewModel)
        return (
            select(counterpart.id)
            .where(
                counterpart.transaction_id == m.ReviewModel.transaction_id,
                counterpart.reviewer_id == m.ReviewModel.reviewee_id,
                counterpart.reviewee_id == m.ReviewModel.reviewer_id,
            )
            .correlate(m.ReviewModel)
            .exists()
        )

    async def add(self, review: ent.Review) -> ent.Review:
        self._s.add(
            m.ReviewModel(
                id=review.id,
                transaction_id=review.transaction_id,
                listing_id=review.listing_id,
                reviewer_id=review.reviewer_id,
                reviewee_id=review.reviewee_id,
                rating=review.rating,
                comment=review.comment,
                created_at=review.created_at,
            )
        )
        await self._s.flush()
        return review

    async def get_by_transaction_and_reviewer(
        self, transaction_id: UUID, reviewer_id: UUID
    ) -> ent.Review | None:
        stmt = select(m.ReviewModel).where(
            m.ReviewModel.transaction_id == transaction_id,
            m.ReviewModel.reviewer_id == reviewer_id,
        )
        row = (await self._s.execute(stmt)).scalar_one_or_none()
        return map_.to_review(row) if row else None

    async def list_for_transaction(self, transaction_id: UUID) -> list[ent.Review]:
        stmt = (
            select(m.ReviewModel)
            .where(m.ReviewModel.transaction_id == transaction_id)
            .order_by(m.ReviewModel.created_at.asc())
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_review(r) for r in rows]

    async def list_visible_for_seller(
        self, seller_id: UUID, *, limit: int = 20, offset: int = 0
    ) -> list[ent.Review]:
        stmt = (
            select(m.ReviewModel)
            .where(
                m.ReviewModel.reviewee_id == seller_id,
                self._counterpart_exists(),
            )
            .order_by(m.ReviewModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [map_.to_review(r) for r in rows]

    async def get_rating_summary(self, seller_id: UUID) -> ent.SellerRatingSummary:
        stmt = select(func.avg(m.ReviewModel.rating), func.count(m.ReviewModel.id)).where(
            m.ReviewModel.reviewee_id == seller_id,
            self._counterpart_exists(),
        )
        average, count = (await self._s.execute(stmt)).one()
        return ent.SellerRatingSummary(
            seller_id=seller_id,
            average_rating=float(average) if average is not None else None,
            review_count=int(count),
        )


class SqlTrustScoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _version_of(self, model_id: UUID) -> str:
        return (
            await self._s.execute(
                select(m.ScoringModelRow.version).where(m.ScoringModelRow.id == model_id)
            )
        ).scalar_one()

    async def get(self, score_id: UUID) -> ent.TrustScore | None:
        row = await self._s.get(m.TrustScoreModel, score_id)
        if row is None:
            return None
        return map_.to_trust_score(row, model_version=await self._version_of(row.scoring_model_id))

    async def get_current(self, seller_id: UUID) -> ent.TrustScore | None:
        row = (
            await self._s.execute(
                select(m.TrustScoreModel)
                .options(selectinload(m.TrustScoreModel.signals))
                .where(m.TrustScoreModel.seller_id == seller_id, m.TrustScoreModel.is_current)
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        return map_.to_trust_score(row, model_version=await self._version_of(row.scoring_model_id))

    async def replace_current(self, score: ent.TrustScore) -> ent.TrustScore:
        """Demote the previous score and insert the new one, atomically.

        The demote MUST happen before the insert: `uq_trust_scores_current` is
        a partial unique index, and inserting first would violate it.
        """
        await self._s.execute(
            update(m.TrustScoreModel)
            .where(m.TrustScoreModel.seller_id == score.seller_id, m.TrustScoreModel.is_current)
            .values(is_current=False)
        )
        await self._s.flush()

        row = m.TrustScoreModel(
            id=score.id,
            seller_id=score.seller_id,
            scoring_model_id=score.scoring_model_id,
            score=int(score.score),
            risk_level=score.risk_level,
            raw_score=score.raw_score,
            available_weight=score.available_weight,
            cap_applied=score.cap_applied,
            confidence=float(score.confidence),
            trigger=score.trigger,
            is_current=True,
            is_manual_override=score.is_manual_override,
            override_reason=score.override_reason,
            overridden_by=score.overridden_by,
            computed_at=score.computed_at,
            valid_until=score.valid_until,
        )
        self._s.add(row)
        for signal in score.signals:
            self._s.add(
                m.TrustScoreSignalModel(
                    id=signal.id,
                    trust_score_id=score.id,
                    signal_definition_id=signal.signal_definition_id,
                    signal_code=signal.signal_code.value,
                    category=signal.category,
                    status=signal.status,
                    weight=signal.weight,
                    points_awarded=signal.points_awarded,
                    points_possible=signal.points_possible,
                    confidence=signal.confidence,
                    reason_code=signal.reason_code.value,
                    reason_text=signal.reason_text,
                    evidence=signal.evidence,
                    source_table=signal.source_table,
                    source_id=signal.source_id,
                )
            )
        await self._s.flush()
        return score

    async def list_history(
        self, seller_id: UUID, *, limit: int = 20, before: datetime | None = None
    ) -> list[ent.TrustScore]:
        stmt = (
            select(m.TrustScoreModel)
            .options(selectinload(m.TrustScoreModel.signals))
            .where(m.TrustScoreModel.seller_id == seller_id)
            .order_by(m.TrustScoreModel.computed_at.desc())
            .limit(limit)
        )
        if before is not None:
            stmt = stmt.where(m.TrustScoreModel.computed_at < before)
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            map_.to_trust_score(r, model_version=await self._version_of(r.scoring_model_id))
            for r in rows
        ]


class SqlScoringModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_active(self) -> ent.ScoringModel | None:
        row = (
            await self._s.execute(
                select(m.ScoringModelRow)
                .options(
                    selectinload(m.ScoringModelRow.weights).selectinload(
                        m.ScoringWeightModel.definition
                    )
                )
                .where(m.ScoringModelRow.is_active)
            )
        ).scalar_one_or_none()
        return map_.to_scoring_model(row) if row else None

    async def get(self, model_id: UUID) -> ent.ScoringModel | None:
        row = (
            await self._s.execute(
                select(m.ScoringModelRow)
                .options(
                    selectinload(m.ScoringModelRow.weights).selectinload(
                        m.ScoringWeightModel.definition
                    )
                )
                .where(m.ScoringModelRow.id == model_id)
            )
        ).scalar_one_or_none()
        return map_.to_scoring_model(row) if row else None

    async def get_by_version(self, version: str) -> ent.ScoringModel | None:
        row = (
            await self._s.execute(
                select(m.ScoringModelRow)
                .options(
                    selectinload(m.ScoringModelRow.weights).selectinload(
                        m.ScoringWeightModel.definition
                    )
                )
                .where(m.ScoringModelRow.version == version)
            )
        ).scalar_one_or_none()
        return map_.to_scoring_model(row) if row else None

    async def list_all(self) -> list[ent.ScoringModel]:
        rows = await self._s.execute(
            select(m.ScoringModelRow)
            .options(
                selectinload(m.ScoringModelRow.weights).selectinload(
                    m.ScoringWeightModel.definition
                )
            )
            .order_by(m.ScoringModelRow.created_at.desc())
        )
        return [map_.to_scoring_model(r) for r in rows.scalars().all()]

    async def list_signal_definitions(self) -> list[ent.SignalDefinition]:
        rows = await self._s.execute(
            select(m.SignalDefinitionModel).order_by(m.SignalDefinitionModel.display_order)
        )
        return [map_.to_signal_definition(r) for r in rows.scalars().all()]

    async def create(self, model: ent.ScoringModel) -> ent.ScoringModel:
        self._s.add(
            m.ScoringModelRow(
                id=model.id,
                version=model.version,
                name=model.name,
                description=model.description,
                is_active=False,  # activation is a separate, audited action
                algorithm=model.algorithm,
                config=model.config,
            )
        )
        for weight in model.weights:
            self._s.add(
                m.ScoringWeightModel(
                    id=weight.id,
                    scoring_model_id=model.id,
                    signal_definition_id=weight.signal_definition_id,
                    weight=weight.weight,
                    threshold_config=weight.threshold_config,
                    hard_cap_on_fail=weight.hard_cap_on_fail,
                    is_enabled=weight.is_enabled,
                )
            )
        await self._s.flush()
        return model

    async def update(self, model: ent.ScoringModel) -> ent.ScoringModel:
        await self._s.execute(
            update(m.ScoringModelRow)
            .where(m.ScoringModelRow.id == model.id)
            .values(name=model.name, description=model.description, config=model.config)
        )
        for weight in model.weights:
            await self._s.execute(
                update(m.ScoringWeightModel)
                .where(m.ScoringWeightModel.id == weight.id)
                .values(
                    weight=weight.weight,
                    threshold_config=weight.threshold_config,
                    hard_cap_on_fail=weight.hard_cap_on_fail,
                    is_enabled=weight.is_enabled,
                )
            )
        return model

    async def activate(self, model_id: UUID, *, by: UUID, at: datetime) -> ent.ScoringModel:
        # Deactivate first: uq_scoring_models_active is a partial unique index
        # and would reject two active rows even momentarily.
        await self._s.execute(
            update(m.ScoringModelRow).where(m.ScoringModelRow.is_active).values(is_active=False)
        )
        await self._s.flush()
        await self._s.execute(
            update(m.ScoringModelRow)
            .where(m.ScoringModelRow.id == model_id)
            .values(is_active=True, activated_at=at, activated_by=by)
        )
        await self._s.flush()
        model = await self.get(model_id)
        assert model is not None
        return model


class SqlRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_hash(self, token_hash: bytes) -> ent.RefreshToken | None:
        row = (
            await self._s.execute(
                select(m.RefreshToken)
                .where(m.RefreshToken.token_hash == token_hash)
                # FOR UPDATE: rotation and reuse detection must not interleave,
                # or two concurrent refreshes could both succeed.
                .with_for_update()
            )
        ).scalar_one_or_none()
        return map_.to_refresh_token(row) if row else None

    async def add(self, token: ent.RefreshToken) -> ent.RefreshToken:
        self._s.add(
            m.RefreshToken(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                family_id=token.family_id,
                parent_id=token.parent_id,
                device_id=token.device_id,
                ip_address=token.ip_address,
                user_agent=token.user_agent,
                expires_at=token.expires_at,
                created_at=token.created_at,
            )
        )
        await self._s.flush()
        return token

    async def revoke(self, token_id: UUID, *, at: datetime, reason: str) -> None:
        await self._s.execute(
            update(m.RefreshToken)
            .where(m.RefreshToken.id == token_id, m.RefreshToken.revoked_at.is_(None))
            .values(revoked_at=at, revoked_reason=reason)
        )

    async def revoke_family(self, family_id: UUID, *, at: datetime, reason: str) -> int:
        result = await self._s.execute(
            update(m.RefreshToken)
            .where(m.RefreshToken.family_id == family_id, m.RefreshToken.revoked_at.is_(None))
            .values(revoked_at=at, revoked_reason=reason)
        )
        # A DML statement always yields a CursorResult; only that subclass
        # carries rowcount, and execute() is typed as the general Result.
        return int(cast("CursorResult[Any]", result).rowcount or 0)

    async def revoke_all_for_user(
        self, user_id: UUID, *, at: datetime, reason: str, except_id: UUID | None = None
    ) -> int:
        stmt = (
            update(m.RefreshToken)
            .where(m.RefreshToken.user_id == user_id, m.RefreshToken.revoked_at.is_(None))
            .values(revoked_at=at, revoked_reason=reason)
        )
        if except_id is not None:
            stmt = stmt.where(m.RefreshToken.id != except_id)
        result = await self._s.execute(stmt)
        # A DML statement always yields a CursorResult; only that subclass
        # carries rowcount, and execute() is typed as the general Result.
        return int(cast("CursorResult[Any]", result).rowcount or 0)

    async def list_active_for_user(self, user_id: UUID) -> list[ent.RefreshToken]:
        rows = await self._s.execute(
            select(m.RefreshToken).where(
                m.RefreshToken.user_id == user_id, m.RefreshToken.revoked_at.is_(None)
            )
        )
        return [map_.to_refresh_token(r) for r in rows.scalars().all()]

    async def delete_expired(self, *, before: datetime) -> int:
        result = await self._s.execute(
            delete(m.RefreshToken).where(m.RefreshToken.expires_at < before)
        )
        # A DML statement always yields a CursorResult; only that subclass
        # carries rowcount, and execute() is typed as the general Result.
        return int(cast("CursorResult[Any]", result).rowcount or 0)


class SqlVerificationTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_by_hash(
        self, token_hash: bytes, *, purpose: e.TokenPurpose
    ) -> ent.VerificationToken | None:
        row = (
            await self._s.execute(
                select(m.VerificationTokenModel).where(
                    m.VerificationTokenModel.token_hash == token_hash,
                    m.VerificationTokenModel.purpose == purpose,
                )
            )
        ).scalar_one_or_none()
        return map_.to_verification_token(row) if row else None

    async def add(self, token: ent.VerificationToken) -> ent.VerificationToken:
        self._s.add(
            m.VerificationTokenModel(
                id=token.id,
                user_id=token.user_id,
                purpose=token.purpose,
                token_hash=token.token_hash,
                target=token.target,
                expires_at=token.expires_at,
                created_at=token.created_at,
            )
        )
        await self._s.flush()
        return token

    async def consume(self, token_id: UUID, *, at: datetime) -> None:
        await self._s.execute(
            update(m.VerificationTokenModel)
            .where(m.VerificationTokenModel.id == token_id)
            .values(consumed_at=at)
        )

    async def invalidate_for_user(self, user_id: UUID, *, purpose: e.TokenPurpose) -> int:
        result = await self._s.execute(
            update(m.VerificationTokenModel)
            .where(
                m.VerificationTokenModel.user_id == user_id,
                m.VerificationTokenModel.purpose == purpose,
                m.VerificationTokenModel.consumed_at.is_(None),
            )
            .values(consumed_at=func.now())
        )
        # A DML statement always yields a CursorResult; only that subclass
        # carries rowcount, and execute() is typed as the general Result.
        return int(cast("CursorResult[Any]", result).rowcount or 0)


class SqlMfaRecoveryCodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def replace_all(
        self, user_id: UUID, code_hashes: list[bytes], *, created_at: datetime
    ) -> None:
        import uuid_utils

        await self._s.execute(
            delete(m.MfaRecoveryCodeModel).where(m.MfaRecoveryCodeModel.user_id == user_id)
        )
        for code_hash in code_hashes:
            self._s.add(
                m.MfaRecoveryCodeModel(
                    id=UUID(str(uuid_utils.uuid7())),
                    user_id=user_id,
                    code_hash=code_hash,
                    created_at=created_at,
                )
            )
        await self._s.flush()

    async def get_unused_by_hash(self, user_id: UUID, code_hash: bytes) -> UUID | None:
        return (
            await self._s.execute(
                select(m.MfaRecoveryCodeModel.id).where(
                    m.MfaRecoveryCodeModel.user_id == user_id,
                    m.MfaRecoveryCodeModel.code_hash == code_hash,
                    m.MfaRecoveryCodeModel.used_at.is_(None),
                )
            )
        ).scalar_one_or_none()

    async def consume(self, code_id: UUID, *, at: datetime) -> None:
        await self._s.execute(
            update(m.MfaRecoveryCodeModel)
            .where(m.MfaRecoveryCodeModel.id == code_id)
            .values(used_at=at)
        )

    async def count_unused(self, user_id: UUID) -> int:
        result = await self._s.execute(
            select(func.count(m.MfaRecoveryCodeModel.id)).where(
                m.MfaRecoveryCodeModel.user_id == user_id,
                m.MfaRecoveryCodeModel.used_at.is_(None),
            )
        )
        return int(result.scalar_one())


class SqlOtpRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_active(self, user_id: UUID, *, purpose: e.OtpPurpose) -> ent.OtpCode | None:
        row = (
            await self._s.execute(
                select(m.OtpCodeModel)
                .where(
                    m.OtpCodeModel.user_id == user_id,
                    m.OtpCodeModel.purpose == purpose,
                    m.OtpCodeModel.consumed_at.is_(None),
                )
                .order_by(m.OtpCodeModel.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        return map_.to_otp(row) if row else None

    async def add(self, otp: ent.OtpCode) -> ent.OtpCode:
        self._s.add(
            m.OtpCodeModel(
                id=otp.id,
                user_id=otp.user_id,
                phone_number_id=otp.phone_number_id,
                purpose=otp.purpose,
                code_hash=otp.code_hash,
                max_attempts=otp.max_attempts,
                expires_at=otp.expires_at,
                sent_at=otp.sent_at,
                created_at=otp.created_at,
            )
        )
        await self._s.flush()
        return otp

    async def increment_attempts(self, otp_id: UUID) -> int:
        """Atomic increment.

        A read-modify-write here would let concurrent requests brute-force past
        the attempt cap, which is the entire protection on a 6-digit code.
        """
        result = await self._s.execute(
            update(m.OtpCodeModel)
            .where(m.OtpCodeModel.id == otp_id)
            .values(attempts=m.OtpCodeModel.attempts + 1)
            .returning(m.OtpCodeModel.attempts)
        )
        return int(result.scalar_one())

    async def consume(self, otp_id: UUID, *, at: datetime) -> None:
        await self._s.execute(
            update(m.OtpCodeModel).where(m.OtpCodeModel.id == otp_id).values(consumed_at=at)
        )

    async def count_sent_since(self, user_id: UUID, *, since: datetime) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.OtpCodeModel)
                    .where(
                        m.OtpCodeModel.user_id == user_id,
                        m.OtpCodeModel.sent_at >= since,
                    )
                )
            ).scalar_one()
        )


class SqlConsentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def has_granted(self, user_id: UUID, *, consent_type: str) -> bool:
        count = (
            await self._s.execute(
                select(func.count())
                .select_from(m.ConsentModel)
                .where(
                    m.ConsentModel.user_id == user_id,
                    m.ConsentModel.consent_type == consent_type,
                    m.ConsentModel.granted.is_(True),
                    m.ConsentModel.revoked_at.is_(None),
                )
            )
        ).scalar_one()
        return bool(count)

    async def record(self, consent: ent.Consent) -> ent.Consent:
        self._s.add(
            m.ConsentModel(
                id=consent.id,
                user_id=consent.user_id,
                consent_type=consent.consent_type,
                version=consent.version,
                granted=consent.granted,
                granted_at=consent.granted_at,
                ip=consent.ip,
                user_agent=consent.user_agent,
            )
        )
        await self._s.flush()
        return consent

    async def list_for_user(self, user_id: UUID) -> list[ent.Consent]:
        rows = await self._s.execute(
            select(m.ConsentModel).where(m.ConsentModel.user_id == user_id)
        )
        return [
            ent.Consent(
                id=r.id,
                user_id=r.user_id,
                consent_type=r.consent_type,
                version=r.version,
                granted=r.granted,
                granted_at=r.granted_at,
                ip=str(r.ip) if r.ip else None,
                user_agent=r.user_agent,
                revoked_at=r.revoked_at,
            )
            for r in rows.scalars().all()
        ]


class SqlFileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, file_id: UUID) -> ent.StoredFile | None:
        row = await self._s.get(m.StoredFileModel, file_id)
        return map_.to_file(row) if row and row.deleted_at is None else None

    async def add(self, file: ent.StoredFile) -> ent.StoredFile:
        self._s.add(
            m.StoredFileModel(
                id=file.id,
                owner_user_id=file.owner_user_id,
                purpose=file.purpose,
                bucket=file.bucket,
                object_key=file.object_key,
                original_filename=file.original_filename,
                mime_type=file.mime_type,
                size_bytes=file.size_bytes,
                sha256=file.sha256,
                width=file.width,
                height=file.height,
                scan_status=file.scan_status,
                is_encrypted=file.is_encrypted,
                expires_at=file.expires_at,
                created_at=file.created_at,
                updated_at=file.created_at,
            )
        )
        await self._s.flush()
        return file

    async def update(self, file: ent.StoredFile) -> ent.StoredFile:
        await self._s.execute(
            update(m.StoredFileModel)
            .where(m.StoredFileModel.id == file.id)
            .values(
                mime_type=file.mime_type,
                size_bytes=file.size_bytes,
                sha256=file.sha256,
                width=file.width,
                height=file.height,
                scan_status=file.scan_status,
                expires_at=file.expires_at,
            )
        )
        return file

    async def list_expired(self, *, before: datetime, limit: int) -> list[ent.StoredFile]:
        """Files past their retention window. Drives the CNIC purge job."""
        rows = await self._s.execute(
            select(m.StoredFileModel)
            .where(
                m.StoredFileModel.expires_at.isnot(None),
                m.StoredFileModel.expires_at < before,
                m.StoredFileModel.deleted_at.is_(None),
            )
            .limit(limit)
        )
        return [map_.to_file(r) for r in rows.scalars().all()]

    async def mark_deleted(self, file_id: UUID, *, at: datetime) -> None:
        await self._s.execute(
            update(m.StoredFileModel).where(m.StoredFileModel.id == file_id).values(deleted_at=at)
        )


class SqlAppealRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, appeal_id: UUID) -> ent.Appeal | None:
        row = (
            await self._s.execute(
                select(m.AppealModel)
                .options(selectinload(m.AppealModel.messages))
                .where(m.AppealModel.id == appeal_id, m.AppealModel.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        return map_.to_appeal(row) if row else None

    async def add(self, appeal: ent.Appeal) -> ent.Appeal:
        self._s.add(
            m.AppealModel(
                id=appeal.id,
                seller_id=appeal.seller_id,
                trust_score_id=appeal.trust_score_id,
                submitted_by=appeal.submitted_by,
                reason_category=appeal.reason_category,
                reason=appeal.reason,
                status=appeal.status,
                submitted_at=appeal.submitted_at,
                created_at=appeal.created_at,
                updated_at=appeal.created_at,
            )
        )
        await self._s.flush()
        return appeal

    async def update(self, appeal: ent.Appeal) -> ent.Appeal:
        await self._s.execute(
            update(m.AppealModel)
            .where(m.AppealModel.id == appeal.id)
            .values(
                status=appeal.status,
                assigned_to=appeal.assigned_to,
                assigned_at=appeal.assigned_at,
                resolution_note=appeal.resolution_note,
                decision=appeal.decision,
                resulting_score_id=appeal.resulting_score_id,
                resolved_at=appeal.resolved_at,
                resolved_by=appeal.resolved_by,
                version=m.AppealModel.version + 1,
            )
        )
        return appeal

    async def add_message(self, message: ent.AppealMessage) -> ent.AppealMessage:
        self._s.add(
            m.AppealMessageModel(
                id=message.id,
                appeal_id=message.appeal_id,
                sender_id=message.sender_id,
                sender_role=message.sender_role,
                body=message.body,
                is_internal=message.is_internal,
                created_at=message.created_at,
            )
        )
        await self._s.flush()
        return message

    async def list_for_seller(self, seller_id: UUID) -> list[ent.Appeal]:
        rows = await self._s.execute(
            select(m.AppealModel)
            .options(selectinload(m.AppealModel.messages))
            .where(m.AppealModel.seller_id == seller_id, m.AppealModel.deleted_at.is_(None))
            .order_by(m.AppealModel.submitted_at.desc())
        )
        return [map_.to_appeal(r) for r in rows.scalars().all()]

    async def count_open_for_seller(self, seller_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.AppealModel)
                    .where(
                        m.AppealModel.seller_id == seller_id,
                        m.AppealModel.status.in_(
                            [
                                e.AppealStatus.OPEN,
                                e.AppealStatus.UNDER_REVIEW,
                                e.AppealStatus.NEEDS_INFO,
                            ]
                        ),
                        m.AppealModel.deleted_at.is_(None),
                    )
                )
            ).scalar_one()
        )

    async def count_since(self, seller_id: UUID, *, since: datetime) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.AppealModel)
                    .where(
                        m.AppealModel.seller_id == seller_id,
                        m.AppealModel.submitted_at >= since,
                    )
                )
            ).scalar_one()
        )

    async def list_queue(
        self, *, status: e.AppealStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[ent.Appeal]:
        stmt = (
            select(m.AppealModel)
            .options(selectinload(m.AppealModel.messages))
            .where(m.AppealModel.deleted_at.is_(None))
            .order_by(m.AppealModel.submitted_at)
            .limit(limit)
            .offset(offset)
        )
        if status is not None:
            stmt = stmt.where(m.AppealModel.status == status)
        rows = await self._s.execute(stmt)
        return [map_.to_appeal(r) for r in rows.scalars().all()]


class SqlReviewCaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, case_id: UUID) -> ent.ReviewCase | None:
        row = await self._s.get(m.ReviewCaseModel, case_id)
        return map_.to_review_case(row) if row else None

    async def add(self, case: ent.ReviewCase) -> ent.ReviewCase:
        self._s.add(
            m.ReviewCaseModel(
                id=case.id,
                seller_id=case.seller_id,
                case_type=case.case_type,
                priority=case.priority,
                status=case.status,
                trigger_reason=case.trigger_reason,
                related_entity_type=case.related_entity_type,
                related_entity_id=case.related_entity_id,
                created_at=case.created_at,
                updated_at=case.created_at,
            )
        )
        await self._s.flush()
        return case

    async def update(self, case: ent.ReviewCase) -> ent.ReviewCase:
        await self._s.execute(
            update(m.ReviewCaseModel)
            .where(m.ReviewCaseModel.id == case.id)
            .values(
                status=case.status,
                assigned_to=case.assigned_to,
                assigned_at=case.assigned_at,
                decision=case.decision,
                decision_note=case.decision_note,
                resolved_at=case.resolved_at,
                resolved_by=case.resolved_by,
            )
        )
        return case

    async def list_queue(self, *, limit: int = 50, offset: int = 0) -> list[ent.ReviewCase]:
        rows = await self._s.execute(
            select(m.ReviewCaseModel)
            .where(m.ReviewCaseModel.status.in_([e.ReviewStatus.QUEUED, e.ReviewStatus.ASSIGNED]))
            .order_by(m.ReviewCaseModel.priority, m.ReviewCaseModel.created_at)
            .limit(limit)
            .offset(offset)
        )
        return [map_.to_review_case(r) for r in rows.scalars().all()]


class SqlApiClientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, client_id: UUID) -> ent.ApiClient | None:
        row = await self._s.get(m.ApiClientModel, client_id)
        return map_.to_api_client(row) if row and row.deleted_at is None else None

    async def create(self, client: ent.ApiClient) -> ent.ApiClient:
        self._s.add(
            m.ApiClientModel(
                id=client.id,
                name=client.name,
                slug=client.slug,
                marketplace_id=client.marketplace_id,
                contact_email=client.contact_email,
                contact_name=client.contact_name,
                status=client.status,
                rate_limit_tier=client.rate_limit_tier,
                monthly_quota=client.monthly_quota,
                allowed_origins=list(client.allowed_origins),
                allowed_ips=list(client.allowed_ips),
                created_at=client.created_at,
                updated_at=client.created_at,
            )
        )
        await self._s.flush()
        return client

    async def update(self, client: ent.ApiClient) -> ent.ApiClient:
        await self._s.execute(
            update(m.ApiClientModel)
            .where(m.ApiClientModel.id == client.id)
            .values(
                name=client.name,
                status=client.status,
                rate_limit_tier=client.rate_limit_tier,
                monthly_quota=client.monthly_quota,
                allowed_origins=list(client.allowed_origins),
                allowed_ips=list(client.allowed_ips),
            )
        )
        return client

    async def list_all(self) -> list[ent.ApiClient]:
        rows = await self._s.execute(
            _alive(select(m.ApiClientModel), m.ApiClientModel).order_by(
                m.ApiClientModel.created_at.desc()
            )
        )
        return [map_.to_api_client(r) for r in rows.scalars().all()]

    async def get_by_slug(self, slug: str) -> ent.ApiClient | None:
        row = (
            await self._s.execute(
                _alive(select(m.ApiClientModel), m.ApiClientModel).where(
                    m.ApiClientModel.slug == slug
                )
            )
        ).scalar_one_or_none()
        return map_.to_api_client(row) if row else None

    async def get_key_by_prefix(self, prefix: str) -> ent.ApiKey | None:
        row = (
            await self._s.execute(
                _alive(select(m.ApiKeyModel), m.ApiKeyModel).where(
                    m.ApiKeyModel.key_prefix == prefix
                )
            )
        ).scalar_one_or_none()
        return map_.to_api_key(row) if row else None

    async def get_key(self, key_id: UUID) -> ent.ApiKey | None:
        row = await self._s.get(m.ApiKeyModel, key_id)
        return map_.to_api_key(row) if row and row.deleted_at is None else None

    async def list_keys(self, client_id: UUID) -> list[ent.ApiKey]:
        rows = await self._s.execute(
            _alive(select(m.ApiKeyModel), m.ApiKeyModel)
            .where(m.ApiKeyModel.api_client_id == client_id)
            .order_by(m.ApiKeyModel.created_at.desc())
        )
        return [map_.to_api_key(r) for r in rows.scalars().all()]

    async def expire_key(self, key_id: UUID, *, at: datetime) -> None:
        """Set an expiry without revoking.

        This is what makes rotation safe: the old key keeps working for the
        overlap and dies on its own. Revoking instead would take the partner
        down for the length of their deploy, which is why nobody rotates.
        """
        await self._s.execute(
            update(m.ApiKeyModel).where(m.ApiKeyModel.id == key_id).values(expires_at=at)
        )

    async def add_key(self, key: ent.ApiKey) -> ent.ApiKey:
        self._s.add(
            m.ApiKeyModel(
                id=key.id,
                api_client_id=key.api_client_id,
                name=key.name,
                key_prefix=key.key_prefix,
                key_hash=key.key_hash,
                scopes=sorted(key.scopes),
                status=key.status,
                expires_at=key.expires_at,
                created_at=key.created_at,
                updated_at=key.created_at,
            )
        )
        await self._s.flush()
        return key

    async def revoke_key(self, key_id: UUID, *, by: UUID, at: datetime) -> None:
        await self._s.execute(
            update(m.ApiKeyModel)
            .where(m.ApiKeyModel.id == key_id)
            .values(status=e.ApiKeyStatus.REVOKED, revoked_at=at, revoked_by=by)
        )

    async def touch_key(self, key_id: UUID, *, at: datetime, ip: str | None) -> None:
        await self._s.execute(
            update(m.ApiKeyModel)
            .where(m.ApiKeyModel.id == key_id)
            .values(last_used_at=at, last_used_ip=ip)
        )

    async def log_request(self, **kwargs: Any) -> None:
        import uuid_utils

        self._s.add(m.ApiRequestLog(id=UUID(str(uuid_utils.uuid7())), **kwargs))

    async def usage_this_month(self, client_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.ApiRequestLog)
                    .where(
                        m.ApiRequestLog.api_client_id == client_id,
                        m.ApiRequestLog.occurred_at >= func.date_trunc("month", func.now()),
                    )
                )
            ).scalar_one()
        )


class SqlAuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def record(self, entry: ent.AuditLogEntry) -> None:
        self._s.add(
            m.AuditLogModel(
                id=entry.id,
                actor_id=entry.actor_id,
                actor_type=e.ActorType(entry.actor_type),
                action=entry.action,
                entity_type=entry.entity_type,
                entity_id=entry.entity_id,
                before=entry.before,
                after=entry.after,
                ip=entry.ip,
                user_agent=entry.user_agent,
                request_id=entry.request_id,
                occurred_at=entry.occurred_at,
            )
        )

    async def list_for_entity(
        self, *, entity_type: str, entity_id: UUID, limit: int = 50
    ) -> list[ent.AuditLogEntry]:
        rows = await self._s.execute(
            select(m.AuditLogModel)
            .where(
                m.AuditLogModel.entity_type == entity_type,
                m.AuditLogModel.entity_id == entity_id,
            )
            .order_by(m.AuditLogModel.occurred_at.desc())
            .limit(limit)
        )
        return [_to_audit(r) for r in rows.scalars().all()]

    async def search(self, **filters: Any) -> list[ent.AuditLogEntry]:
        stmt = select(m.AuditLogModel).order_by(m.AuditLogModel.occurred_at.desc())
        if actor_id := filters.get("actor_id"):
            stmt = stmt.where(m.AuditLogModel.actor_id == actor_id)
        if action := filters.get("action"):
            stmt = stmt.where(m.AuditLogModel.action == action)
        if entity_type := filters.get("entity_type"):
            stmt = stmt.where(m.AuditLogModel.entity_type == entity_type)
        stmt = stmt.limit(int(filters.get("limit", 100)))
        rows = await self._s.execute(stmt)
        return [_to_audit(r) for r in rows.scalars().all()]


def _to_audit(row: m.AuditLogModel) -> ent.AuditLogEntry:
    return ent.AuditLogEntry(
        id=row.id,
        action=row.action,
        entity_type=row.entity_type,
        occurred_at=row.occurred_at,
        actor_id=row.actor_id,
        actor_type=row.actor_type.value,
        entity_id=row.entity_id,
        before=row.before,
        after=row.after,
        ip=str(row.ip) if row.ip else None,
        user_agent=row.user_agent,
        request_id=row.request_id,
    )


class SqlJobRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, job_id: UUID) -> ent.JobRun | None:
        row = await self._s.get(m.JobRunModel, job_id)
        return map_.to_job_run(row) if row else None

    async def get_by_key(self, job_key: str) -> ent.JobRun | None:
        row = (
            await self._s.execute(select(m.JobRunModel).where(m.JobRunModel.job_key == job_key))
        ).scalar_one_or_none()
        return map_.to_job_run(row) if row else None

    async def add(self, job: ent.JobRun) -> ent.JobRun:
        self._s.add(
            m.JobRunModel(
                id=job.id,
                job_name=job.job_name,
                job_key=job.job_key,
                status=e.JobStatus(job.status),
                related_entity_type=job.related_entity_type,
                related_entity_id=job.related_entity_id,
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                payload=job.payload,
                request_id=job.request_id,
                queued_at=job.queued_at,
            )
        )
        await self._s.flush()
        return job

    async def update(self, job: ent.JobRun) -> ent.JobRun:
        await self._s.execute(
            update(m.JobRunModel)
            .where(m.JobRunModel.id == job.id)
            .values(
                status=e.JobStatus(job.status),
                attempt=job.attempt,
                result=job.result,
                error_message=job.error_message,
                error_type=job.error_type,
                started_at=job.started_at,
                finished_at=job.finished_at,
                duration_ms=job.duration_ms,
            )
        )
        return job

    async def list_dead_letters(self, *, limit: int = 50) -> list[ent.JobRun]:
        """Exhausted jobs. Surfaced in the admin panel - silent job loss is
        unacceptable when the outcome affects a seller's score."""
        rows = await self._s.execute(
            select(m.JobRunModel)
            .where(m.JobRunModel.status == e.JobStatus.DEAD)
            .order_by(m.JobRunModel.queued_at.desc())
            .limit(limit)
        )
        return [map_.to_job_run(r) for r in rows.scalars().all()]


class SqlNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def add(self, notification: ent.Notification) -> ent.Notification:
        self._s.add(
            m.NotificationModel(
                id=notification.id,
                user_id=notification.user_id,
                type=notification.type,
                title=notification.title,
                body=notification.body,
                data=dict(notification.data),
                channel=notification.channel,
                created_at=notification.created_at,
            )
        )
        await self._s.flush()
        return notification

    async def list_for_user(
        self, user_id: UUID, *, unread_only: bool = False, limit: int = 50
    ) -> list[ent.Notification]:
        stmt = (
            select(m.NotificationModel)
            .where(m.NotificationModel.user_id == user_id)
            .order_by(m.NotificationModel.created_at.desc())
            .limit(limit)
        )
        if unread_only:
            stmt = stmt.where(m.NotificationModel.read_at.is_(None))
        rows = await self._s.execute(stmt)
        return [map_.to_notification(r) for r in rows.scalars().all()]

    async def count_unread(self, user_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.NotificationModel)
                    .where(
                        m.NotificationModel.user_id == user_id,
                        m.NotificationModel.read_at.is_(None),
                    )
                )
            ).scalar_one()
        )

    async def mark_read(self, notification_id: UUID, *, user_id: UUID, at: datetime) -> None:
        await self._s.execute(
            update(m.NotificationModel)
            .where(
                m.NotificationModel.id == notification_id, m.NotificationModel.user_id == user_id
            )
            .values(read_at=at)
        )

    async def mark_all_read(self, user_id: UUID, *, at: datetime) -> int:
        result = await self._s.execute(
            update(m.NotificationModel)
            .where(m.NotificationModel.user_id == user_id, m.NotificationModel.read_at.is_(None))
            .values(read_at=at)
        )
        # A DML statement always yields a CursorResult; only that subclass
        # carries rowcount, and execute() is typed as the general Result.
        return int(cast("CursorResult[Any]", result).rowcount or 0)


__all__ = [
    "SqlApiClientRepository",
    "SqlAppealRepository",
    "SqlAuditLogRepository",
    "SqlConsentRepository",
    "SqlDeviceRepository",
    "SqlEmailRepository",
    "SqlFileRepository",
    "SqlIdentityRepository",
    "SqlJobRunRepository",
    "SqlListingRepository",
    "SqlNotificationRepository",
    "SqlOtpRepository",
    "SqlPhoneRepository",
    "SqlRefreshTokenRepository",
    "SqlReviewCaseRepository",
    "SqlScoringModelRepository",
    "SqlSellerRepository",
    "SqlTrustScoreRepository",
    "SqlUserRepository",
    "SqlVerificationTokenRepository",
]
