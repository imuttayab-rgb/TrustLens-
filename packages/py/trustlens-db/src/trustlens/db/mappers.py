"""ORM row <-> domain entity mapping.

This module is the reason `trustlens.core` never imports SQLAlchemy. Every
repository converts at its edge, so a use case only ever sees domain entities
and the in-memory test fakes are behaviourally equivalent to the real thing.

The cost is boilerplate. The benefit is that the scoring engine can be tested
exhaustively without a database, and that swapping the persistence layer would
not touch a single business rule.
"""

from __future__ import annotations

from typing import Any

from trustlens.core.domain import entities as ent
from trustlens.core.domain import enums as e
from trustlens.core.domain.value_objects import Confidence, Email, Money, PhoneE164, Score
from trustlens.db import models as m


def to_user(row: m.User) -> ent.User:
    role_keys = frozenset(link.role.key for link in row.roles) or frozenset({row.primary_role})
    permissions = frozenset(rp.permission.key for link in row.roles for rp in link.role.permissions)
    return ent.User(
        id=row.id,
        email=Email(row.email),
        full_name=row.full_name,
        status=row.status,
        primary_role=row.primary_role,
        roles=role_keys,
        permissions=permissions,
        created_at=row.created_at,
        email_verified_at=row.email_verified_at,
        mfa_enabled=row.mfa_enabled,
        failed_login_count=row.failed_login_count,
        locked_until=row.locked_until,
        last_login_at=row.last_login_at,
        password_changed_at=row.password_changed_at,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
        version=row.version,
    )


def to_seller(row: m.SellerProfile) -> ent.SellerProfile:
    return ent.SellerProfile(
        id=row.id,
        user_id=row.user_id,
        handle=row.handle,
        display_name=row.display_name,
        account_opened_at=row.account_opened_at,
        created_at=row.created_at,
        marketplace_id=row.marketplace_id,
        external_seller_ref=row.external_seller_ref,
        business_type=row.business_type,
        city=row.city,
        country_code=row.country_code,
        bio=row.bio,
        current_trust_score_id=row.current_trust_score_id,
        identity_status=row.identity_status,
        phone_status=row.phone_status,
        email_status=row.email_status,
        is_flagged=row.is_flagged,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
        version=row.version,
    )


def to_identity_document(row: m.IdentityDocumentModel) -> ent.IdentityDocument:
    return ent.IdentityDocument(
        id=row.id,
        seller_id=row.seller_id,
        document_type=row.document_type,
        file_id=row.file_id,
        status=row.status,
        created_at=row.created_at,
        ocr_engine=row.ocr_engine,
        ocr_engine_version=row.ocr_engine_version,
        ocr_confidence=float(row.ocr_confidence) if row.ocr_confidence is not None else None,
        ocr_raw=row.ocr_raw or {},
        fields=ent.OcrFields(
            full_name=row.extracted_name,
            # The CNIC number itself is never mapped into the domain: it is
            # decrypted only where it is genuinely needed (OCR confirmation),
            # so an accidental log or serialisation cannot leak it.
            expiry_date=row.extracted_expiry,
        ),
        extracted_cnic_hash=row.extracted_cnic_hash,
        quality_score=float(row.quality_score) if row.quality_score is not None else None,
        rejection_reason=row.rejection_reason,
        processed_at=row.processed_at,
    )


def to_identity_verification(row: m.IdentityVerificationModel) -> ent.IdentityVerification:
    return ent.IdentityVerification(
        id=row.id,
        seller_id=row.seller_id,
        decision=row.decision,
        created_at=row.created_at,
        front_document_id=row.front_document_id,
        back_document_id=row.back_document_id,
        selfie_document_id=row.selfie_document_id,
        face_match_engine=row.face_match_engine,
        engine_version=row.engine_version,
        face_similarity=float(row.face_similarity) if row.face_similarity is not None else None,
        face_distance=float(row.face_distance) if row.face_distance is not None else None,
        threshold_used=float(row.threshold_used) if row.threshold_used is not None else None,
        liveness_passed=row.liveness_passed,
        name_match_score=(
            float(row.name_match_score) if row.name_match_score is not None else None
        ),
        decision_source=row.decision_source,
        decided_by=row.decided_by,
        decision_reason=row.decision_reason,
        raw_result=row.raw_result or {},
        verified_at=row.verified_at,
    )


def to_phone(row: m.PhoneNumberModel) -> ent.PhoneNumber:
    return ent.PhoneNumber(
        id=row.id,
        user_id=row.user_id,
        e164=PhoneE164(row.e164),
        created_at=row.created_at,
        is_primary=row.is_primary,
        verified_at=row.verified_at,
        carrier_name=row.carrier_name,
        line_type=row.line_type,
        is_disposable=row.is_disposable,
        country_code=row.country_code,
        lookup_raw=row.lookup_raw or {},
        lookup_at=row.lookup_at,
        deleted_at=row.deleted_at,
    )


def to_email(row: m.EmailAddressModel) -> ent.EmailAddress:
    return ent.EmailAddress(
        id=row.id,
        user_id=row.user_id,
        email=Email(row.email),
        created_at=row.created_at,
        is_primary=row.is_primary,
        verified_at=row.verified_at,
        is_disposable=row.is_disposable,
        mx_valid=row.mx_valid,
        domain_age_days=row.domain_age_days,
        lookup_raw=row.lookup_raw or {},
        lookup_at=row.lookup_at,
        deleted_at=row.deleted_at,
    )


def to_device(row: m.DeviceModel) -> ent.Device:
    return ent.Device(
        id=row.id,
        fingerprint_hash=row.fingerprint_hash,
        first_seen_at=row.first_seen_at,
        last_seen_at=row.last_seen_at,
        user_agent=row.user_agent,
        browser=row.browser,
        os=row.os,
        device_type=row.device_type,
        screen_resolution=row.screen_resolution,
        timezone=row.timezone,
        is_bot=row.is_bot,
        is_emulator=row.is_emulator,
    )


def to_ip_reputation(row: m.IpAddressModel) -> ent.IpReputation:
    return ent.IpReputation(
        ip=str(row.ip),
        country_code=row.country_code,
        region=row.region,
        city=row.city,
        asn=row.asn,
        asn_org=row.asn_org,
        is_vpn=row.is_vpn,
        is_proxy=row.is_proxy,
        is_tor=row.is_tor,
        is_datacenter=row.is_datacenter,
        abuse_score=row.abuse_score,
        provider=row.provider,
        looked_up_at=row.looked_up_at,
        raw=row.lookup_raw or {},
    )


def to_access_event(row: m.AccessEventModel) -> ent.AccessEvent:
    return ent.AccessEvent(
        id=row.id,
        event_type=row.event_type,
        occurred_at=row.occurred_at,
        user_id=row.user_id,
        device_id=row.device_id,
        ip_address_id=row.ip_address_id,
        ip=str(row.ip) if row.ip else None,
        request_id=row.request_id,
        user_agent=row.user_agent,
    )


def to_listing(row: m.ListingModel, analysis: ent.ListingAnalysis | None = None) -> ent.Listing:
    return ent.Listing(
        id=row.id,
        seller_id=row.seller_id,
        title=row.title,
        description=row.description,
        status=row.status,
        source=row.source,
        created_at=row.created_at,
        marketplace_id=row.marketplace_id,
        external_listing_ref=row.external_listing_ref,
        price=(
            Money(float(row.price), row.currency)
            if row.price is not None and row.currency
            else None
        ),
        category=row.category,
        condition=row.condition,
        city=row.city,
        area=row.area,
        latitude=float(row.latitude) if row.latitude is not None else None,
        longitude=float(row.longitude) if row.longitude is not None else None,
        country_code=row.country_code,
        external_url=row.external_url,
        posted_at=row.posted_at,
        latest_analysis=analysis,
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
        version=row.version,
    )


def to_listing_analysis(row: m.ListingAnalysisModel) -> ent.ListingAnalysis:
    labels_raw: Any = row.labels or []
    labels = tuple(
        ent.ScamLabel(
            code=str(item.get("code", "")),
            confidence=float(item.get("confidence", 0.0)),
            evidence=item.get("evidence"),
        )
        if isinstance(item, dict)
        else ent.ScamLabel(code=str(item), confidence=1.0)
        for item in labels_raw
    )
    return ent.ListingAnalysis(
        id=row.id,
        listing_id=row.listing_id,
        analyzer_type=row.analyzer_type,
        provider=row.provider,
        model_name=row.model_name,
        risk_score=float(row.risk_score),
        confidence=float(row.confidence),
        analysed_at=row.analysed_at,
        model_version=row.model_version,
        prompt_version=row.prompt_version,
        labels=labels,
        findings=row.findings or {},
        price_deviation_pct=(
            float(row.price_deviation_pct) if row.price_deviation_pct is not None else None
        ),
        raw_response=row.raw_response or {},
        input_tokens=row.input_tokens,
        output_tokens=row.output_tokens,
        latency_ms=row.latency_ms,
        cost_usd=float(row.cost_usd),
    )


def to_listing_image(row: m.ListingImageModel) -> ent.ListingImage:
    return ent.ListingImage(
        id=row.id,
        listing_id=row.listing_id,
        file_id=row.file_id,
        position=row.position,
        created_at=row.created_at,
        width=row.width,
        height=row.height,
        perceptual_hash=row.perceptual_hash,
        sha256=row.sha256,
        is_primary=row.is_primary,
    )


def to_signal_definition(row: m.SignalDefinitionModel) -> ent.SignalDefinition:
    return ent.SignalDefinition(
        id=row.id,
        code=e.SignalCode(row.code),
        category=row.category,
        name=row.name,
        description=row.description,
        buyer_facing_description=row.buyer_facing_description,
        max_points=row.max_points,
        is_active=row.is_active,
        is_critical=row.is_critical,
        display_order=row.display_order,
    )


def to_scoring_model(row: m.ScoringModelRow) -> ent.ScoringModel:
    return ent.ScoringModel(
        id=row.id,
        version=row.version,
        name=row.name,
        description=row.description,
        is_active=row.is_active,
        algorithm=row.algorithm,
        config=row.config or {},
        weights=tuple(
            ent.ScoringWeight(
                id=w.id,
                scoring_model_id=w.scoring_model_id,
                signal_definition_id=w.signal_definition_id,
                signal_code=e.SignalCode(w.definition.code),
                weight=float(w.weight),
                threshold_config=w.threshold_config or {},
                hard_cap_on_fail=w.hard_cap_on_fail,
                is_enabled=w.is_enabled,
            )
            for w in row.weights
        ),
        activated_at=row.activated_at,
        activated_by=row.activated_by,
    )


def to_trust_score(row: m.TrustScoreModel, *, model_version: str) -> ent.TrustScore:
    return ent.TrustScore(
        id=row.id,
        seller_id=row.seller_id,
        scoring_model_id=row.scoring_model_id,
        scoring_model_version=model_version,
        score=Score(row.score),
        risk_level=row.risk_level,
        raw_score=float(row.raw_score),
        available_weight=float(row.available_weight),
        confidence=Confidence(float(row.confidence)),
        trigger=row.trigger,
        computed_at=row.computed_at,
        valid_until=row.valid_until,
        signals=tuple(to_trust_score_signal(s) for s in row.signals),
        cap_applied=row.cap_applied,
        is_current=row.is_current,
        is_manual_override=row.is_manual_override,
        override_reason=row.override_reason,
        overridden_by=row.overridden_by,
    )


def to_trust_score_signal(row: m.TrustScoreSignalModel) -> ent.TrustScoreSignal:
    return ent.TrustScoreSignal(
        id=row.id,
        trust_score_id=row.trust_score_id,
        signal_definition_id=row.signal_definition_id,
        signal_code=e.SignalCode(row.signal_code),
        category=row.category,
        status=row.status,
        weight=float(row.weight),
        points_awarded=float(row.points_awarded),
        points_possible=float(row.points_possible),
        confidence=float(row.confidence),
        reason_code=e.ReasonCode(row.reason_code),
        reason_text=row.reason_text,
        evidence=row.evidence or {},
        source_table=row.source_table,
        source_id=row.source_id,
    )


def to_appeal(row: m.AppealModel) -> ent.Appeal:
    return ent.Appeal(
        id=row.id,
        seller_id=row.seller_id,
        trust_score_id=row.trust_score_id,
        submitted_by=row.submitted_by,
        reason_category=row.reason_category,
        reason=row.reason,
        status=row.status,
        submitted_at=row.submitted_at,
        created_at=row.created_at,
        assigned_to=row.assigned_to,
        assigned_at=row.assigned_at,
        resolution_note=row.resolution_note,
        decision=row.decision,
        resulting_score_id=row.resulting_score_id,
        resolved_at=row.resolved_at,
        resolved_by=row.resolved_by,
        messages=tuple(
            ent.AppealMessage(
                id=msg.id,
                appeal_id=msg.appeal_id,
                sender_id=msg.sender_id,
                sender_role=msg.sender_role,
                body=msg.body,
                created_at=msg.created_at,
                is_internal=msg.is_internal,
            )
            for msg in row.messages
        ),
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
        version=row.version,
    )


def to_review_case(row: m.ReviewCaseModel) -> ent.ReviewCase:
    return ent.ReviewCase(
        id=row.id,
        seller_id=row.seller_id,
        case_type=row.case_type,
        status=row.status,
        created_at=row.created_at,
        priority=row.priority,
        trigger_reason=row.trigger_reason,
        related_entity_type=row.related_entity_type,
        related_entity_id=row.related_entity_id,
        assigned_to=row.assigned_to,
        assigned_at=row.assigned_at,
        decision=row.decision,
        decision_note=row.decision_note,
        resolved_at=row.resolved_at,
        resolved_by=row.resolved_by,
    )


def to_report(row: m.ReportModel) -> ent.Report:
    return ent.Report(
        id=row.id,
        reporter_id=row.reporter_id,
        target_type=row.target_type,
        target_id=row.target_id,
        category=row.category,
        description=row.description,
        status=row.status,
        created_at=row.created_at,
        resolved_at=row.resolved_at,
        resolved_by=row.resolved_by,
        resolution_note=row.resolution_note,
        updated_at=row.updated_at,
    )


def to_block(row: m.BlockModel) -> ent.Block:
    return ent.Block(
        id=row.id,
        blocker_id=row.blocker_id,
        blocked_id=row.blocked_id,
        created_at=row.created_at,
    )


def to_offer(row: m.OfferModel) -> ent.Offer:
    return ent.Offer(
        id=row.id,
        conversation_id=row.conversation_id,
        listing_id=row.listing_id,
        buyer_id=row.buyer_id,
        seller_id=row.seller_id,
        offered_by=row.offered_by,
        amount=float(row.amount),
        currency=row.currency,
        status=row.status,
        created_at=row.created_at,
        expires_at=row.expires_at,
        message=row.message,
        parent_offer_id=row.parent_offer_id,
        responded_at=row.responded_at,
    )


def to_transaction(row: m.TransactionModel) -> ent.Transaction:
    return ent.Transaction(
        id=row.id,
        listing_id=row.listing_id,
        buyer_id=row.buyer_id,
        seller_id=row.seller_id,
        offer_id=row.offer_id,
        amount=float(row.amount),
        currency=row.currency,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
        completed_at=row.completed_at,
        cancelled_at=row.cancelled_at,
        cancel_reason=row.cancel_reason,
    )


def to_api_client(row: m.ApiClientModel) -> ent.ApiClient:
    return ent.ApiClient(
        id=row.id,
        name=row.name,
        slug=row.slug,
        contact_email=row.contact_email,
        status=row.status,
        created_at=row.created_at,
        marketplace_id=row.marketplace_id,
        contact_name=row.contact_name,
        rate_limit_tier=row.rate_limit_tier,
        monthly_quota=row.monthly_quota,
        allowed_origins=tuple(row.allowed_origins or ()),
        allowed_ips=tuple(str(ip) for ip in (row.allowed_ips or ())),
        updated_at=row.updated_at,
        deleted_at=row.deleted_at,
    )


def to_api_key(row: m.ApiKeyModel) -> ent.ApiKey:
    return ent.ApiKey(
        id=row.id,
        api_client_id=row.api_client_id,
        name=row.name,
        key_prefix=row.key_prefix,
        key_hash=row.key_hash,
        status=row.status,
        created_at=row.created_at,
        scopes=frozenset(row.scopes or ()),
        last_used_at=row.last_used_at,
        last_used_ip=str(row.last_used_ip) if row.last_used_ip else None,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )


def to_refresh_token(row: m.RefreshToken) -> ent.RefreshToken:
    return ent.RefreshToken(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        family_id=row.family_id,
        expires_at=row.expires_at,
        created_at=row.created_at,
        parent_id=row.parent_id,
        device_id=row.device_id,
        ip_address=str(row.ip_address) if row.ip_address else None,
        user_agent=row.user_agent,
        revoked_at=row.revoked_at,
        revoked_reason=row.revoked_reason,
    )


def to_verification_token(row: m.VerificationTokenModel) -> ent.VerificationToken:
    return ent.VerificationToken(
        id=row.id,
        user_id=row.user_id,
        purpose=row.purpose,
        token_hash=row.token_hash,
        target=row.target,
        expires_at=row.expires_at,
        created_at=row.created_at,
        consumed_at=row.consumed_at,
    )


def to_otp(row: m.OtpCodeModel) -> ent.OtpCode:
    return ent.OtpCode(
        id=row.id,
        user_id=row.user_id,
        phone_number_id=row.phone_number_id,
        purpose=row.purpose,
        code_hash=row.code_hash,
        expires_at=row.expires_at,
        created_at=row.created_at,
        attempts=row.attempts,
        max_attempts=row.max_attempts,
        consumed_at=row.consumed_at,
        sent_at=row.sent_at,
    )


def to_file(row: m.StoredFileModel) -> ent.StoredFile:
    return ent.StoredFile(
        id=row.id,
        purpose=row.purpose,
        bucket=row.bucket,
        object_key=row.object_key,
        mime_type=row.mime_type,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        created_at=row.created_at,
        owner_user_id=row.owner_user_id,
        original_filename=row.original_filename,
        width=row.width,
        height=row.height,
        scan_status=row.scan_status,
        is_encrypted=row.is_encrypted,
        expires_at=row.expires_at,
        deleted_at=row.deleted_at,
    )


def to_job_run(row: m.JobRunModel) -> ent.JobRun:
    return ent.JobRun(
        id=row.id,
        job_name=row.job_name,
        status=row.status.value,
        queued_at=row.queued_at,
        job_key=row.job_key,
        related_entity_type=row.related_entity_type,
        related_entity_id=row.related_entity_id,
        attempt=row.attempt,
        max_attempts=row.max_attempts,
        payload=row.payload or {},
        result=row.result,
        error_message=row.error_message,
        error_type=row.error_type,
        request_id=row.request_id,
        started_at=row.started_at,
        finished_at=row.finished_at,
        duration_ms=row.duration_ms,
    )


def to_notification(row: m.NotificationModel) -> ent.Notification:
    return ent.Notification(
        id=row.id,
        user_id=row.user_id,
        type=row.type,
        title=row.title,
        body=row.body,
        created_at=row.created_at,
        channel=row.channel,
        data=row.data or {},
        read_at=row.read_at,
        sent_at=row.sent_at,
    )


__all__ = [name for name in dir() if name.startswith("to_")]
