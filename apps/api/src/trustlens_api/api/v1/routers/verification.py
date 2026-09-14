"""Verification endpoints (features F1-F4).

The upload path is the highest-risk surface in the system, so it is worth
being explicit about the flow:

    1. POST /files/upload-intent  -> presigned PUT URL + file_id
    2. Client PUTs the bytes straight to object storage (never through us)
    3. POST /verification/identity references the file_ids
    4. The API validates ownership, size and MAGIC BYTES, then enqueues a job

Step 2 is what keeps image bytes out of the API process entirely - no memory
exhaustion vector, and a much smaller container.
"""

from __future__ import annotations

import hashlib
from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status

from trustlens.core.application.use_cases.verification import (
    RequestOtpCommand,
    RequestPhoneOtp,
    SubmitIdentityCommand,
    SubmitIdentityDocuments,
    VerifyOtpCommand,
    VerifyPhoneOtp,
)
from trustlens.core.domain.entities import (
    AuthenticatedActor,
    Consent,
    IdentityDocument,
    StoredFile,
)
from trustlens.core.domain.enums import ConsentType, FilePurpose
from trustlens.core.domain.errors import PermissionDenied, RateLimitExceeded, ValidationError
from trustlens.shared.logging import get_logger
from trustlens_api.api.deps import (
    ActorDep,
    ContainerDep,
    MetaDep,
    SellerDep,
    UowDep,
    require_permissions,
)
from trustlens_api.api.v1.schemas.common import JobAccepted, envelope
from trustlens_api.api.v1.schemas.verification import (
    DeviceFingerprintRequest,
    IdentityStatusResponse,
    RequestOtpRequest,
    RequestOtpResponse,
    SubmitIdentityRequest,
    UploadIntentRequest,
    UploadIntentResponse,
    VerificationChecklistItem,
    VerificationStatusResponse,
    VerifyOtpRequest,
)


def _require_user_id(actor: AuthenticatedActor) -> UUID:
    """These flows belong to a person, not a principal.

    `user_id` is optional because an API client and a system job are also
    actors; neither can own a phone number, a device or a consent record.
    """
    if actor.user_id is None:
        raise PermissionDenied()
    return actor.user_id


log = get_logger(__name__)

router = APIRouter(tags=["Verification"])


async def _throttle_otp_request(container: ContainerDep, meta: MetaDep) -> None:
    """Per-IP limit on top of the use case's per-account hourly/daily caps
    (VER-02) - those alone do nothing about many throwaway accounts each
    requesting SMS from the same address. Fails open, same policy as every
    other limiter here."""
    limits = container.settings.rate_limit
    if not limits.enabled or meta.ip is None:
        return
    try:
        allowed, _remaining, retry_after = await container.rate_limiter.hit(
            f"otp-request:ip:{meta.ip}",
            limit=limits.otp_request_per_ip_per_hour,
            window_seconds=3600,
        )
    except Exception:
        log.warning("otp_request_throttle_unavailable_failing_open", ip=meta.ip)
        return
    if not allowed:
        raise RateLimitExceeded(
            "Too many verification codes requested from this network. Try again later.",
            retry_after=retry_after,
        )


#: Points each check is worth under scoring model v1, shown in the checklist so
#: a seller can see what completing it buys them.
CHECKLIST = (
    ("identity", "Government ID and selfie", 30, "/dashboard/verification/identity"),
    ("phone", "Phone number", 15, "/dashboard/verification/phone"),
    ("email", "Email address", 10, "/dashboard/verification/email"),
    ("device", "Device and network", 20, None),
)


@router.post(
    "/files/upload-intent",
    summary="Get a presigned upload URL",
    description=(
        "Returns a short-lived presigned URL. The client uploads directly to "
        "object storage; bytes never pass through the API."
    ),
)
async def upload_intent(
    body: UploadIntentRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    settings = container.settings.storage

    try:
        purpose = FilePurpose(body.purpose)
    except ValueError:
        raise ValidationError("Unknown upload purpose.", field="purpose") from None

    # A listing video is the one upload purpose that isn't a still image -
    # its own, larger size cap and its own mime allowlist, so a 50 MB video
    # doesn't require raising the shared 10 MB cap for CNIC/selfie/appeal
    # uploads too.
    is_video = purpose == FilePurpose.LISTING_VIDEO
    max_bytes = (
        settings.storage_max_video_upload_bytes if is_video else settings.storage_max_upload_bytes
    )
    allowed_mime = (
        settings.storage_allowed_video_mime if is_video else settings.storage_allowed_mime
    )
    extensions = (
        {"video/mp4": "mp4"}
        if is_video
        else {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    )

    if body.size_bytes > max_bytes:
        raise ValidationError(
            f"Files must be {max_bytes // 1_048_576} MB or smaller.", field="sizeBytes"
        )
    if body.content_type not in allowed_mime:
        raise ValidationError(
            "MP4 only." if is_video else "Only JPEG, PNG and WEBP images are accepted.",
            field="contentType",
        )

    file_id = container.ids.new()
    bucket = (
        settings.storage_bucket_documents
        if purpose.is_sensitive
        else settings.storage_bucket_listings
    )
    extension = extensions[body.content_type]
    # Server-generated key. The client's filename is metadata only and is
    # never used as a path component - that is a path-traversal vector.
    object_key = f"{purpose.value.lower()}/{actor.user_id}/{file_id}.{extension}"

    presigned = await container.storage.presign_upload(
        bucket=bucket,
        object_key=object_key,
        content_type=body.content_type,
        max_bytes=max_bytes,
        ttl_seconds=settings.storage_presign_ttl_seconds,
    )

    now = container.clock.now()
    await uow.files.add(
        StoredFile(
            id=file_id,
            purpose=purpose,
            bucket=bucket,
            object_key=object_key,
            mime_type=body.content_type,
            size_bytes=body.size_bytes,
            sha256=b"",  # filled in by the worker after it reads the object
            created_at=now,
            owner_user_id=_require_user_id(actor),
            original_filename=body.filename,
            # Sensitive media carries its retention deadline from the moment
            # it is created, so the purge job needs no special-casing.
            expires_at=(
                now + timedelta(days=settings.media_retention_days_identity)
                if purpose.is_sensitive
                else None
            ),
        )
    )
    await uow.commit()

    return envelope(
        UploadIntentResponse(
            file_id=file_id,
            upload_url=presigned.url,
            fields=presigned.fields,
            expires_at=presigned.expires_at,
            max_bytes=settings.storage_max_upload_bytes,
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post(
    "/verification/identity",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit CNIC and selfie for verification",
    description=(
        "Records the submission and queues OCR + face matching. Returns "
        "immediately with a job id - the AI pipeline takes 15-30 seconds and "
        "runs in the worker (ADR-0003)."
    ),
    dependencies=[Depends(require_permissions("identity:submit"))],
)
async def submit_identity(
    body: SubmitIdentityRequest,
    actor: ActorDep,
    seller: SellerDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    now = container.clock.now()

    # Record biometric consent BEFORE the use case checks for it. Comparing a
    # face against a national ID photo without recorded, versioned consent is
    # not acceptable regardless of jurisdiction.
    if not await uow.consents.has_granted(
        actor.user_id, consent_type=ConsentType.BIOMETRIC_PROCESSING.value
    ):
        await uow.consents.record(
            Consent(
                id=container.ids.new(),
                user_id=_require_user_id(actor),
                consent_type=ConsentType.BIOMETRIC_PROCESSING,
                version="1.0",
                granted=True,
                granted_at=now,
                ip=meta.ip,
                user_agent=meta.user_agent,
            )
        )
        await uow.flush()

    result = await SubmitIdentityDocuments(
        uow=uow, queue=container.queue, clock=container.clock, ids=container.ids
    ).execute(
        SubmitIdentityCommand(
            seller_id=seller.id,
            cnic_front_file_id=body.cnic_front_file_id,
            cnic_back_file_id=body.cnic_back_file_id,
            selfie_file_id=body.selfie_file_id,
        )
    )

    return envelope(
        JobAccepted(job_id=result.job_id, poll_url=f"/api/v1/jobs/{result.job_id}").model_dump(
            by_alias=True
        ),
        request_id=meta.request_id,
    )


@router.get("/verification/identity", summary="Identity verification status")
async def identity_status(seller: SellerDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    verification = await uow.identities.get_latest_verification(seller.id)
    documents = await uow.identities.list_documents(seller.id)
    front = next((d for d in documents if d.document_type.value == "CNIC_FRONT"), None)

    return envelope(
        IdentityStatusResponse(
            status=seller.identity_status.value,
            verification_id=verification.id if verification else None,
            similarity=verification.face_similarity if verification else None,
            threshold=verification.threshold_used if verification else None,
            decision_reason=verification.decision_reason if verification else None,
            extracted_name=front.fields.full_name if front else None,
            # Never the full number - only the masked form ever leaves the DB.
            cnic_masked=_mask_cnic(front) if front else None,
            expiry_date=str(front.fields.expiry_date)
            if front and front.fields.expiry_date
            else None,
            submitted_at=front.created_at if front else None,
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post("/verification/phone/request-otp", summary="Send a phone verification code")
async def request_otp(
    body: RequestOtpRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    await _throttle_otp_request(container, meta)
    notifications = container.settings.notifications
    result = await RequestPhoneOtp(
        uow=uow,
        otp=container.otp_generator,
        queue=container.queue,
        clock=container.clock,
        ids=container.ids,
        code_length=notifications.otp_length,
        ttl_seconds=notifications.otp_ttl_seconds,
        max_attempts=notifications.otp_max_attempts,
        limit_per_hour=notifications.otp_send_limit_hour,
        limit_per_day=notifications.otp_send_limit_day,
        # Only ever true with the console sender, i.e. local development, so
        # the offline demo can complete the flow.
        expose_debug_code=notifications.sms_provider == "console"
        and not container.settings.env.is_deployed,
    ).execute(RequestOtpCommand(user_id=_require_user_id(actor), phone_number=body.phone_number))

    return envelope(
        RequestOtpResponse(
            phone_number_id=result.phone_number_id,
            masked_number=result.masked_number,
            expires_at=result.expires_at,
            debug_code=result.debug_code,
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post("/verification/phone/verify-otp", summary="Confirm a phone verification code")
async def verify_otp(
    body: VerifyOtpRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    result = await VerifyPhoneOtp(
        uow=uow, otp=container.otp_generator, queue=container.queue, clock=container.clock
    ).execute(VerifyOtpCommand(user_id=_require_user_id(actor), code=body.code))

    return envelope(
        {"phoneNumberId": str(result.phone_number_id), "verified": result.verified},
        request_id=meta.request_id,
    )


@router.post("/verification/device", summary="Submit a device fingerprint")
async def submit_device(
    body: DeviceFingerprintRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    from trustlens.core.domain.entities import AccessEvent, Device, DeviceLink

    now = container.clock.now()
    # Hashed, not stored raw: the fingerprint is client-supplied and is a
    # correlation key, not a secret we need to read back.
    fingerprint_hash = hashlib.sha256(body.fingerprint.encode()).digest()

    device = await uow.devices.upsert(
        Device(
            id=container.ids.new(),
            fingerprint_hash=fingerprint_hash,
            first_seen_at=now,
            last_seen_at=now,
            user_agent=body.user_agent or meta.user_agent,
            screen_resolution=body.screen_resolution,
            timezone=body.timezone,
        )
    )
    await uow.devices.link(
        DeviceLink(
            user_id=_require_user_id(actor),
            device_id=device.id,
            first_seen_at=now,
            last_seen_at=now,
        )
    )
    await uow.devices.record_access(
        AccessEvent(
            id=container.ids.new(),
            event_type="VERIFY",
            occurred_at=now,
            user_id=_require_user_id(actor),
            device_id=device.id,
            ip=meta.ip,
            request_id=meta.request_id,
            user_agent=meta.user_agent,
        )
    )
    await uow.commit()

    # IP enrichment is a metered third-party call; the user must not wait for it.
    if meta.ip:
        await container.queue.enqueue("network.enrich_ip", ip=meta.ip)

    seller = await uow.sellers.get_by_user(actor.user_id)
    if seller is not None:
        await container.queue.enqueue(
            "scoring.recompute_trust_score",
            seller_id=str(seller.id),
            trigger="SIGNAL_CHANGE",
        )

    return envelope({"deviceId": str(device.id), "recorded": True}, request_id=meta.request_id)


@router.get("/verification/status", summary="All verification checks in one call")
async def verification_status(seller: SellerDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    devices = await uow.devices.list_for_user(seller.user_id)
    statuses = {
        "identity": seller.identity_status.value,
        "phone": seller.phone_status.value,
        "email": seller.email_status.value,
        "device": "VERIFIED" if devices else "NOT_STARTED",
    }

    return envelope(
        VerificationStatusResponse(
            **statuses,
            checklist=[
                VerificationChecklistItem(
                    key=key,
                    label=label,
                    status=statuses[key],
                    points_available=points,
                    action_url=url,
                )
                for key, label, points, url in CHECKLIST
            ],
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


def _mask_cnic(document: IdentityDocument) -> str | None:
    """The domain entity never carries the number; only its presence is known."""
    return "*****-*****XX-X" if document.extracted_cnic_hash else None


__all__ = ["router"]
