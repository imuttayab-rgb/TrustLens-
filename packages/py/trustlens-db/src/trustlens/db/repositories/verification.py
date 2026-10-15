"""Verification repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import date, datetime
from uuid import UUID
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from trustlens.core.domain import entities as ent
from trustlens.core.domain import enums as e
from trustlens.core.domain.value_objects import PhoneE164
from trustlens.db import mappers as map_
from trustlens.db import models as m
from .common import _alive


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
                raw_result=verification.raw_result,
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

    async def list_verified_sellers_with_lapsed_id(
        self, *, today: date, excluded_engines: tuple[str, ...], limit: int
    ) -> list[UUID]:
        """Pre-filter for the expiry sweep; the use case re-checks each seller.

        Only CNIC sides with a real OCR engine and a stored expiry before
        today are considered, so fake/demo OCR rows can never revoke anyone.
        """
        rows = await self._s.execute(
            select(m.IdentityDocumentModel.seller_id)
            .join(m.SellerProfile, m.SellerProfile.id == m.IdentityDocumentModel.seller_id)
            .where(
                m.SellerProfile.identity_status == e.VerificationStatus.VERIFIED,
                m.SellerProfile.deleted_at.is_(None),
                m.IdentityDocumentModel.deleted_at.is_(None),
                m.IdentityDocumentModel.document_type.in_(
                    (e.DocumentType.CNIC_FRONT, e.DocumentType.CNIC_BACK)
                ),
                m.IdentityDocumentModel.extracted_expiry.is_not(None),
                m.IdentityDocumentModel.extracted_expiry < today,
                m.IdentityDocumentModel.ocr_engine.is_not(None),
                m.IdentityDocumentModel.ocr_engine.not_in(excluded_engines),
            )
            .distinct()
            .limit(limit)
        )
        return list(rows.scalars().all())


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


class SqlFileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def check_upload_budget(
        self, user_id: UUID, *, requested_bytes: int, max_bytes: int, max_files: int
    ) -> None:
        """Reserve capacity in the same transaction as adding the upload intent.

        The user row serializes concurrent reservations. Pending intents count,
        so unfinished uploads cannot bypass the account's storage quota.
        """
        from trustlens.core.domain.errors import RateLimitExceeded

        await self._s.execute(select(m.User.id).where(m.User.id == user_id).with_for_update())
        count, used = (
            await self._s.execute(
                select(
                    func.count(m.StoredFileModel.id),
                    func.coalesce(func.sum(m.StoredFileModel.size_bytes), 0),
                ).where(
                    m.StoredFileModel.owner_user_id == user_id,
                    m.StoredFileModel.deleted_at.is_(None),
                )
            )
        ).one()
        if count >= max_files or used + requested_bytes > max_bytes:
            raise RateLimitExceeded(
                "Upload storage limit reached. Contact support to review your quota.",
                retry_after=3600,
            )

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
