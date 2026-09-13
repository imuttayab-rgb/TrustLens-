"""Admin review queue endpoints (feature F7).

Every route here is permission-gated, not merely role-gated. A reviewer works
the queue but deliberately cannot override a score; that separation exists in
the seeded permissions and is enforced per route rather than per router, so
adding a route cannot silently inherit a wider grant than it needs.
"""

from __future__ import annotations

import dataclasses
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field

from trustlens.core.application.use_cases.admin import (
    MIN_DECISION_NOTE_CHARS,
    ClaimReviewCase,
    ClaimReviewCaseCommand,
    DecideReviewCase,
    DecideReviewCaseCommand,
    ListReviewQueue,
)
from trustlens.core.application.use_cases.moderation import (
    ListReportQueue,
    ResolveReport,
    ResolveReportCommand,
)
from trustlens.core.application.use_cases.safemeet import (
    CreateMeetingVenue,
    CreateMeetingVenueCommand,
    ListMeetingVenuesAdmin,
    SetVenueActive,
)
from trustlens.core.application.use_cases.scoring import GetTrustScore, GetTrustScoreCommand
from trustlens.core.domain.entities import (
    AuditLogEntry,
    AuthenticatedActor,
    ReviewCase,
    ScoringModel,
    ScoringWeight,
)
from trustlens.core.domain.enums import DocumentType, ReportStatus, RiskLevel
from trustlens.core.domain.errors import (
    ConflictError,
    EntityNotFound,
    PermissionDenied,
    ValidationError,
)
from trustlens.db.queries import SellerAdminQueries
from trustlens_api.api.deps import (
    ActorDep,
    ContainerDep,
    MetaDep,
    PageDep,
    UowDep,
    require_permissions,
)
from trustlens_api.api.v1.routers.trust_scores import trust_score_to_response
from trustlens_api.api.v1.schemas.common import PageMeta, Schema, envelope

router = APIRouter(prefix="/admin", tags=["admin"])


class SellerSearchModel(Schema):
    id: UUID
    handle: str
    display_name: str
    email: str
    city: str | None
    identity_status: str
    phone_status: str
    email_status: str
    is_flagged: bool
    score: int | None
    risk_level: str | None
    updated_at: Any


class SellerDetailModel(SellerSearchModel):
    score_history: list[dict[str, Any]]


class AdminSummaryModel(Schema):
    total_sellers: int
    low_risk: int
    medium_risk: int
    high_risk: int
    unknown_risk: int
    flagged: int


class ScoringWeightModel(Schema):
    signal_code: str
    weight: float
    hard_cap_on_fail: int | None
    is_enabled: bool


class ScoringModelResponse(Schema):
    id: UUID
    version: str
    name: str
    description: str
    is_active: bool
    algorithm: str
    total_weight: float
    weights: list[ScoringWeightModel]
    activated_at: Any


class ScoringWeightInput(BaseModel):
    signal_code: str
    weight: float = Field(ge=0)
    hard_cap_on_fail: int | None = Field(default=None, ge=0, le=100)
    is_enabled: bool = True
    threshold_config: dict[str, Any] = Field(default_factory=dict)


class CreateScoringModelRequest(BaseModel):
    version: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2_000)
    algorithm: str = Field(default="WEIGHTED_SUM", max_length=30)
    weights: list[ScoringWeightInput] = Field(min_length=1)


class IdentityReviewDocumentModel(Schema):
    document_type: str
    status: str
    preview_url: str
    url_expires_at: Any
    ocr_confidence: float | None
    quality_score: float | None
    extracted_name: str | None
    expiry_date: Any


class IdentityReviewModel(Schema):
    seller_id: UUID
    verification_id: UUID
    decision: str
    decision_source: str
    face_match_engine: str | None
    face_similarity: float | None
    face_distance: float | None
    threshold_used: float | None
    liveness_passed: bool | None
    name_match_score: float | None
    decision_reason: str | None
    documents: list[IdentityReviewDocumentModel]


class ReviewCaseModel(BaseModel):
    id: UUID
    seller_id: UUID
    case_type: str
    status: str
    priority: int
    created_at: Any
    trigger_reason: str | None = None
    related_entity_type: str | None = None
    related_entity_id: UUID | None = None
    assigned_to: UUID | None = None
    decision: str | None = None
    decision_note: str | None = None


class DecideReviewRequest(BaseModel):
    approve: bool
    note: str = Field(
        min_length=MIN_DECISION_NOTE_CHARS,
        max_length=2_000,
        description=(
            "Why this decision was made. Mandatory because a human verdict "
            "changes someone's Trust Score and must stay explainable to them."
        ),
    )


def _reviewer_id(actor: AuthenticatedActor) -> UUID:
    """A review decision must be attributable to a person.

    `user_id` is optional because an API client and a system job are also
    principals, and neither may decide a case: the audit trail would name
    nobody, and the seller could not be told who judged them.
    """
    if actor.user_id is None:
        raise PermissionDenied("review_case:decide")
    return actor.user_id


def _to_model(case: ReviewCase) -> ReviewCaseModel:
    return ReviewCaseModel(
        id=case.id,
        seller_id=case.seller_id,
        case_type=case.case_type.value,
        status=case.status.value,
        priority=case.priority,
        created_at=case.created_at,
        trigger_reason=case.trigger_reason,
        related_entity_type=case.related_entity_type,
        related_entity_id=case.related_entity_id,
        assigned_to=case.assigned_to,
        decision=case.decision,
        decision_note=case.decision_note,
    )


def _to_scoring_model(model: Any) -> ScoringModelResponse:
    return ScoringModelResponse(
        id=model.id,
        version=model.version,
        name=model.name,
        description=model.description,
        is_active=model.is_active,
        algorithm=model.algorithm,
        total_weight=model.total_weight,
        weights=[
            ScoringWeightModel(
                signal_code=weight.signal_code.value,
                weight=weight.weight,
                hard_cap_on_fail=weight.hard_cap_on_fail,
                is_enabled=weight.is_enabled,
            )
            for weight in model.weights
        ],
        activated_at=model.activated_at,
    )


@router.get(
    "/scoring-models",
    summary="List scoring model versions",
    dependencies=[Depends(require_permissions("scoring_model:read"))],
)
async def list_scoring_models(uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    models = await uow.scoring_models.list_all()
    return envelope(
        [_to_scoring_model(model).model_dump(by_alias=True) for model in models],
        request_id=meta.request_id,
    )


@router.post(
    "/scoring-models",
    summary="Author a new scoring model version",
    description=(
        "Creates a new version as a draft (never active - activation is a "
        "separate, audited action via POST .../activate). Every submitted "
        "signal_code must match a known, active SignalDefinition: silently "
        "dropping an unrecognised code here, the way scoring itself does for "
        "safety, would let a model pass the sum-to-100 check while actually "
        "scoring against fewer than 100 points of real signals."
    ),
    dependencies=[Depends(require_permissions("scoring_model:write"))],
    status_code=status.HTTP_201_CREATED,
)
async def create_scoring_model(
    body: CreateScoringModelRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    if actor.user_id is None:
        raise PermissionDenied("scoring_model:write")
    if await uow.scoring_models.get_by_version(body.version) is not None:
        raise ConflictError(f"a scoring model version {body.version!r} already exists")

    definitions = {d.code.value: d for d in await uow.scoring_models.list_signal_definitions()}

    seen_codes: set[str] = set()
    resolved: list[tuple[ScoringWeightInput, Any]] = []
    for weight_input in body.weights:
        if weight_input.signal_code in seen_codes:
            raise ValidationError(
                f"duplicate signal_code {weight_input.signal_code!r} in weights",
                field="weights",
            )
        seen_codes.add(weight_input.signal_code)
        definition = definitions.get(weight_input.signal_code)
        if definition is None or not definition.is_active:
            raise ValidationError(
                f"{weight_input.signal_code!r} is not a known, active signal",
                field="weights",
            )
        resolved.append((weight_input, definition))

    model_id = container.ids.new()
    model = ScoringModel(
        id=model_id,
        version=body.version,
        name=body.name,
        description=body.description,
        is_active=False,
        algorithm=body.algorithm,
        weights=tuple(
            ScoringWeight(
                id=container.ids.new(),
                scoring_model_id=model_id,
                signal_definition_id=definition.id,
                signal_code=definition.code,
                weight=weight_input.weight,
                threshold_config=weight_input.threshold_config,
                hard_cap_on_fail=weight_input.hard_cap_on_fail,
                is_enabled=weight_input.is_enabled,
            )
            for weight_input, definition in resolved
        ),
    )
    # Same rule ComputeTrustScore relies on (enabled weights sum to 100) -
    # checked before this draft ever reaches the database.
    model.validate()

    created = await uow.scoring_models.create(model)
    await uow.audit_logs.record(
        AuditLogEntry(
            id=container.ids.new(),
            action="scoring_model.created",
            entity_type="scoring_models",
            entity_id=model_id,
            actor_id=actor.user_id,
            occurred_at=container.clock.now(),
            before={},
            after={"version": created.version, "weight_count": len(created.weights)},
        )
    )
    await uow.commit()
    return envelope(
        _to_scoring_model(created).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.post(
    "/scoring-models/{model_id}/activate",
    summary="Activate a scoring model version",
    dependencies=[Depends(require_permissions("scoring_model:activate"))],
)
async def activate_scoring_model(
    model_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    if actor.user_id is None:
        raise PermissionDenied("scoring_model:activate")
    model = await uow.scoring_models.get(model_id)
    if model is None:
        raise EntityNotFound("scoring_model", model_id)
    model.validate()
    previous = await uow.scoring_models.get_active()
    activated = await uow.scoring_models.activate(
        model_id, by=actor.user_id, at=container.clock.now()
    )
    await uow.audit_logs.record(
        AuditLogEntry(
            id=container.ids.new(),
            action="scoring_model.activated",
            entity_type="scoring_models",
            entity_id=model_id,
            actor_id=actor.user_id,
            occurred_at=container.clock.now(),
            before={"version": previous.version if previous else None},
            after={"version": activated.version},
        )
    )
    await uow.commit()
    await container.queue.enqueue(
        "scoring.bulk_recompute_for_model", model_version=activated.version
    )
    return envelope(
        _to_scoring_model(activated).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.get(
    "/dashboard/summary",
    summary="Get admin seller summary",
    dependencies=[Depends(require_permissions("seller:read:any"))],
)
async def get_dashboard_summary(uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    summary = await SellerAdminQueries(uow.session).summary()
    return envelope(
        AdminSummaryModel(
            total_sellers=summary.total,
            low_risk=summary.low,
            medium_risk=summary.medium,
            high_risk=summary.high,
            unknown_risk=summary.unknown,
            flagged=summary.flagged,
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.get(
    "/sellers",
    summary="Search sellers",
    dependencies=[Depends(require_permissions("seller:read:any"))],
)
async def search_sellers(
    uow: UowDep,
    page: PageDep,
    meta: MetaDep,
    search: str | None = Query(default=None, max_length=120),
    risk_level: RiskLevel | None = Query(default=None, alias="riskLevel"),
    flagged: bool | None = Query(default=None),
) -> dict[str, Any]:
    bounded_search = search.strip() if search else None
    rows, total = await SellerAdminQueries(uow.session).search(
        search=bounded_search,
        risk_level=risk_level,
        flagged=flagged,
        limit=page.per_page,
        offset=page.offset,
    )
    return envelope(
        [SellerSearchModel(**dataclasses.asdict(row)).model_dump(by_alias=True) for row in rows],
        request_id=meta.request_id,
        pagination=PageMeta.build(page=page.page, per_page=page.per_page, total=total),
    )


@router.get(
    "/sellers/{seller_id}",
    summary="Get seller details",
    dependencies=[Depends(require_permissions("seller:read:any"))],
)
async def get_seller_detail(
    seller_id: UUID,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    row = await SellerAdminQueries(uow.session).get(seller_id)
    if row is None:
        raise EntityNotFound("seller", seller_id)
    history = await uow.trust_scores.list_history(seller_id, limit=20)
    detail = SellerDetailModel(
        **dataclasses.asdict(row),
        score_history=[
            {
                "id": score.id,
                "score": int(score.score),
                "riskLevel": score.risk_level.value,
                "modelVersion": score.scoring_model_version,
                "trigger": score.trigger.value,
                "computedAt": score.computed_at,
                "manualOverride": score.is_manual_override,
            }
            for score in history
        ],
    )
    return envelope(detail.model_dump(by_alias=True), request_id=meta.request_id)


@router.get(
    "/sellers/{seller_id}/trust-score",
    summary="Get a seller's full trust-score breakdown",
    description=(
        "The same per-signal breakdown a seller sees on their own dashboard, "
        "reachable from the seller-detail page without opening a review case. "
        "Gated on trust_score:read:full rather than reusing the seller-facing "
        "route directly, so this admin-side read stays a routed, auditable "
        "grant instead of an implicit side effect of seller:read:any."
    ),
    dependencies=[Depends(require_permissions("trust_score:read:full"))],
)
async def get_seller_trust_score(
    seller_id: UUID,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    seller = await uow.sellers.get(seller_id)
    if seller is None:
        raise EntityNotFound("seller", seller_id)

    detail = await GetTrustScore(uow=uow).execute(
        GetTrustScoreCommand(seller_id=seller_id, include_improvements=False)
    )
    return envelope(
        trust_score_to_response(detail.score).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.get(
    "/sellers/{seller_id}/identity-review",
    summary="Review identity evidence",
    dependencies=[Depends(require_permissions("identity:read:any"))],
)
async def get_identity_review(
    seller_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    seller = await uow.sellers.get(seller_id)
    if seller is None:
        raise EntityNotFound("seller", seller_id)

    verification = await uow.identities.get_latest_verification(seller_id)
    if verification is None:
        raise EntityNotFound("identity_verification", seller_id)

    document_ids = (
        (DocumentType.CNIC_FRONT, verification.front_document_id),
        (DocumentType.CNIC_BACK, verification.back_document_id),
        (DocumentType.SELFIE, verification.selfie_document_id),
    )
    documents = {
        document.id: document for document in await uow.identities.list_documents(seller_id)
    }
    review_documents: list[IdentityReviewDocumentModel] = []
    expires_at = container.clock.now()
    ttl_seconds = container.settings.storage.storage_presign_ttl_seconds
    from datetime import timedelta

    expires_at += timedelta(seconds=ttl_seconds)
    for document_type, document_id in document_ids:
        if document_id is None or document_id not in documents:
            continue
        document = documents[document_id]
        stored_file = await uow.files.get(document.file_id)
        if stored_file is None:
            continue
        review_documents.append(
            IdentityReviewDocumentModel(
                document_type=document_type.value,
                status=document.status.value,
                preview_url=await container.storage.presign_download(
                    bucket=stored_file.bucket,
                    object_key=stored_file.object_key,
                    ttl_seconds=ttl_seconds,
                ),
                url_expires_at=expires_at,
                ocr_confidence=document.ocr_confidence,
                quality_score=document.quality_score,
                extracted_name=document.fields.full_name,
                expiry_date=document.fields.expiry_date,
            )
        )

    if actor.user_id is not None:
        await uow.audit_logs.record(
            AuditLogEntry(
                id=container.ids.new(),
                action="identity.evidence_viewed",
                entity_type="identity_verifications",
                entity_id=verification.id,
                actor_id=actor.user_id,
                occurred_at=container.clock.now(),
                before={},
                after={"seller_id": str(seller_id), "document_count": len(review_documents)},
            )
        )
        await uow.commit()

    review = IdentityReviewModel(
        seller_id=seller_id,
        verification_id=verification.id,
        decision=verification.decision.value,
        decision_source=verification.decision_source,
        face_match_engine=verification.face_match_engine,
        face_similarity=verification.face_similarity,
        face_distance=verification.face_distance,
        threshold_used=verification.threshold_used,
        liveness_passed=verification.liveness_passed,
        name_match_score=verification.name_match_score,
        decision_reason=verification.decision_reason,
        documents=review_documents,
    )
    return envelope(review.model_dump(by_alias=True), request_id=meta.request_id)


@router.get(
    "/review-cases",
    summary="The review queue",
    dependencies=[Depends(require_permissions("review_case:read"))],
)
async def list_review_cases(uow: UowDep, page: PageDep, meta: MetaDep) -> dict[str, Any]:
    result = await ListReviewQueue(uow=uow).execute(limit=page.per_page, offset=page.offset)
    return envelope(
        [_to_model(case).model_dump(by_alias=True) for case in result.items],
        request_id=meta.request_id,
    )


@router.post(
    "/review-cases/{case_id}/claim",
    summary="Claim a case before working on it",
    description=(
        "Claiming is what stops two reviewers deciding the same case "
        "differently. A case already assigned to someone else is refused."
    ),
    dependencies=[Depends(require_permissions("review_case:decide"))],
)
async def claim_review_case(
    case_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    case = await ClaimReviewCase(uow=uow, clock=container.clock, ids=container.ids).execute(
        ClaimReviewCaseCommand(case_id=case_id, reviewer_id=_reviewer_id(actor))
    )
    return envelope(_to_model(case).model_dump(by_alias=True), request_id=meta.request_id)


@router.post(
    "/review-cases/{case_id}/decide",
    summary="Record a decision on a case",
    description=(
        "Records a verdict and enqueues a rescore. It never writes a score "
        "directly - the scoring policy stays the only thing that produces a "
        "number (ADR-0002). The decision and its reason are audit-logged in "
        "the same transaction."
    ),
    dependencies=[Depends(require_permissions("review_case:decide"))],
)
async def decide_review_case(
    case_id: UUID,
    body: DecideReviewRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    result = await DecideReviewCase(
        uow=uow, queue=container.queue, clock=container.clock, ids=container.ids
    ).execute(
        DecideReviewCaseCommand(
            case_id=case_id,
            reviewer_id=_reviewer_id(actor),
            approve=body.approve,
            note=body.note,
        )
    )
    return envelope(
        {
            "case": _to_model(result.case).model_dump(by_alias=True),
            "identityUpdated": result.identity_updated,
        },
        request_id=meta.request_id,
    )


class AuditLogEntryModel(Schema):
    id: Any
    action: str
    entity_type: str
    entity_id: Any
    actor_id: Any
    actor_type: str
    before: Any
    after: Any
    ip: str | None
    user_agent: str | None
    request_id: str | None
    occurred_at: Any


class AdminReportModel(Schema):
    id: UUID
    reporter_id: UUID
    target_type: str
    target_id: UUID
    category: str
    description: str
    status: str
    created_at: Any
    resolved_at: Any
    resolved_by: UUID | None
    resolution_note: str | None


class ResolveReportRequest(BaseModel):
    status: str
    resolution_note: str | None = Field(default=None, max_length=2_000)


def _to_admin_report(report: Any) -> AdminReportModel:
    return AdminReportModel(
        id=report.id,
        reporter_id=report.reporter_id,
        target_type=report.target_type.value,
        target_id=report.target_id,
        category=report.category.value,
        description=report.description,
        status=report.status.value,
        created_at=report.created_at,
        resolved_at=report.resolved_at,
        resolved_by=report.resolved_by,
        resolution_note=report.resolution_note,
    )


@router.get(
    "/audit-logs",
    summary="List admin audit log entries",
    description=(
        "Every admin action that changes a seller's state is recorded here. "
        "Entries are immutable once written. Filter by actor, action, entity "
        "type or date range to find what happened and who did it."
    ),
    dependencies=[Depends(require_permissions("seller:read:any"))],
)
async def list_audit_logs(
    uow: UowDep,
    meta: MetaDep,
    actor_id: UUID | None = Query(default=None, alias="actorId"),
    action: str | None = Query(default=None, max_length=100),
    entity_type: str | None = Query(default=None, alias="entityType", max_length=80),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    filters: dict[str, Any] = {"limit": limit}
    if actor_id is not None:
        filters["actor_id"] = actor_id
    if action:
        filters["action"] = action.strip()
    if entity_type:
        filters["entity_type"] = entity_type.strip()
    entries = await uow.audit_logs.search(**filters)
    return envelope(
        [
            AuditLogEntryModel(
                id=e.id,
                action=e.action,
                entity_type=e.entity_type,
                entity_id=e.entity_id,
                actor_id=e.actor_id,
                actor_type=e.actor_type,
                before=e.before,
                after=e.after,
                ip=e.ip,
                user_agent=e.user_agent,
                request_id=e.request_id,
                occurred_at=e.occurred_at,
            ).model_dump(by_alias=True)
            for e in entries
        ],
        request_id=meta.request_id,
    )


@router.get(
    "/reports",
    summary="The reports queue (MOD-01)",
    description=(
        "Every user-filed report against a listing, seller, or message. "
        "Separate from the identity-review/appeal queues above - those are "
        "about a score decision, this is content/conduct moderation."
    ),
    dependencies=[Depends(require_permissions("moderation:read"))],
)
async def list_report_queue(
    uow: UowDep,
    meta: MetaDep,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    status_value = ReportStatus(status_filter) if status_filter else None
    page = await ListReportQueue(uow=uow).execute(status=status_value, limit=limit, offset=offset)
    return envelope(
        [_to_admin_report(item).model_dump(by_alias=True) for item in page.items],
        request_id=meta.request_id,
        pagination=PageMeta.build(
            page=(page.offset // page.limit) + 1, per_page=page.limit, total=page.total
        ),
    )


@router.post(
    "/reports/{report_id}/resolve",
    summary="Resolve a report",
    dependencies=[Depends(require_permissions("moderation:resolve"))],
)
async def resolve_report(
    report_id: UUID,
    body: ResolveReportRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    if actor.user_id is None:
        raise PermissionDenied("moderation:resolve")
    try:
        status_value = ReportStatus(body.status)
    except ValueError as exc:
        raise ValidationError(f"Invalid status: {body.status}") from exc

    resolved = await ResolveReport(uow=uow, clock=container.clock, ids=container.ids).execute(
        ResolveReportCommand(
            report_id=report_id,
            resolver_id=actor.user_id,
            status=status_value,
            resolution_note=body.resolution_note,
        )
    )
    return envelope(
        _to_admin_report(resolved).model_dump(by_alias=True), request_id=meta.request_id
    )


class AdminMeetingVenueModel(Schema):
    id: UUID
    name: str
    address: str
    city: str
    area: str | None
    latitude: float
    longitude: float
    is_active: bool
    notes: str | None
    created_at: Any


class CreateMeetingVenueRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: str = Field(min_length=1, max_length=500)
    city: str = Field(min_length=1, max_length=100)
    area: str | None = Field(default=None, max_length=100)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    notes: str | None = Field(default=None, max_length=1_000)


def _to_admin_venue(venue: Any) -> AdminMeetingVenueModel:
    return AdminMeetingVenueModel(
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


@router.get(
    "/meeting-venues",
    summary="The curated SafeMeet venue catalogue (SAFE-01)",
    dependencies=[Depends(require_permissions("safemeet:manage"))],
)
async def list_meeting_venues(
    uow: UowDep,
    meta: MetaDep,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    venues = await ListMeetingVenuesAdmin(uow=uow).execute(limit=limit, offset=offset)
    return envelope(
        [_to_admin_venue(v).model_dump(by_alias=True) for v in venues],
        request_id=meta.request_id,
    )


@router.post(
    "/meeting-venues",
    status_code=status.HTTP_201_CREATED,
    summary="Add a public meetup spot to the catalogue",
    dependencies=[Depends(require_permissions("safemeet:manage"))],
)
async def create_meeting_venue(
    body: CreateMeetingVenueRequest, container: ContainerDep, uow: UowDep, meta: MetaDep
) -> dict[str, Any]:
    venue = await CreateMeetingVenue(uow=uow, clock=container.clock, ids=container.ids).execute(
        CreateMeetingVenueCommand(
            name=body.name,
            address=body.address,
            city=body.city,
            area=body.area,
            latitude=body.latitude,
            longitude=body.longitude,
            notes=body.notes,
        )
    )
    return envelope(_to_admin_venue(venue).model_dump(by_alias=True), request_id=meta.request_id)


@router.post(
    "/meeting-venues/{venue_id}/activate",
    summary="Reactivate a meeting venue",
    dependencies=[Depends(require_permissions("safemeet:manage"))],
)
async def activate_meeting_venue(venue_id: UUID, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    venue = await SetVenueActive(uow=uow).execute(venue_id, is_active=True)
    return envelope(_to_admin_venue(venue).model_dump(by_alias=True), request_id=meta.request_id)


@router.post(
    "/meeting-venues/{venue_id}/deactivate",
    summary="Deactivate a meeting venue - it stops being suggested, past meetups are unaffected",
    dependencies=[Depends(require_permissions("safemeet:manage"))],
)
async def deactivate_meeting_venue(venue_id: UUID, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    venue = await SetVenueActive(uow=uow).execute(venue_id, is_active=False)
    return envelope(_to_admin_venue(venue).model_dump(by_alias=True), request_id=meta.request_id)


__all__ = ["router"]
