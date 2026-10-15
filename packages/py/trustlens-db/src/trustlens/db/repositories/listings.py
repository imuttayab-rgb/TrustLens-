"""Listings repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from trustlens.core.catalogue import NODES, descendants, validate_facets
from trustlens.core.catalogue.search import search_tokens
import dataclasses
from datetime import datetime
from typing import Any
from uuid import UUID
from sqlalchemy import Select, and_, case, delete, func, or_, select, update
from sqlalchemy import cast as sql_cast
from sqlalchemy.ext.asyncio import AsyncSession
from trustlens.core.domain import entities as ent
from trustlens.core.domain import enums as e
from trustlens.db import mappers as map_
from trustlens.db import models as m
from trustlens.db.photo_guard import photos_cleared
from trustlens.db.profiles import listing_not_paused, listing_profile_ready
from .common import _alive


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
        category_node_id: str | None = None,
        facets: dict | None = None,
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
        condition: str | None = None,
        min_trust_score: int | None = None,
        max_trust_score: int | None = None,
        verified_only: bool = False,
    ) -> Select[Any]:
        stmt = (
            select(
                m.ListingModel,
                m.SellerProfile,
                m.TrustScoreModel.risk_level,
                m.TrustScoreModel.score,
            )
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
            # The listing worker also keeps unapproved sellers' items in DRAFT,
            # but the buyer query must fail closed for older ACTIVE rows and
            # verification changes racing a listing analysis job.
            m.SellerProfile.identity_status == e.VerificationStatus.VERIFIED,
            m.SellerProfile.phone_status == e.VerificationStatus.VERIFIED,
            m.SellerProfile.email_status == e.VerificationStatus.VERIFIED,
            m.SellerProfile.is_flagged.is_(False),
            photos_cleared(),
            listing_profile_ready(),
            listing_not_paused(),
        )
        if category is not None:
            stmt = stmt.where(m.ListingModel.category == category)
        if category_node_id:
            ids = descendants(category_node_id)
            # Old 'mobiles' explicitly meant 'Mobile phones' (the original
            # LISTING_CATEGORY_LABELS contract). Include only untyped legacy
            # phone ads in that leaf; never move typed accessories/tablets or
            # infer ambiguous Cars/Bikes membership from titles.
            typed = m.ListingModel.category_node_id.in_(ids)
            if category_node_id == "mobiles/mobile-phones":
                typed = or_(
                    typed,
                    and_(
                        m.ListingModel.category_node_id.is_(None),
                        m.ListingModel.category == "mobiles",
                    ),
                )
            if NODES[category_node_id]["parentId"] is None:
                legacy = {NODES[id]["legacyCategory"] for id in ids}
                # Ambiguous legacy 'other' and 'vehicles' cannot honestly assign
                # Jobs vs Kids or Cars vs Bikes. They stay on general Browse.
                legacy -= {"other"}
                if category_node_id != "vehicles":
                    legacy -= {"vehicles"}
                if legacy:
                    typed = or_(
                        typed,
                        and_(
                            m.ListingModel.category_node_id.is_(None),
                            m.ListingModel.category.in_(legacy),
                        ),
                    )
            stmt = stmt.where(typed)
        for key, value in validate_facets(category_node_id, facets).items():
            column = m.ListingModel.category_data[key]
            if isinstance(value, dict):
                # JSON number comparison avoids unsafe casts of old freeform text.
                numeric = case(
                    (func.jsonb_typeof(column) == "number", column.as_float()), else_=None
                )
                if "min" in value:
                    stmt = stmt.where(numeric >= value["min"])
                if "max" in value:
                    stmt = stmt.where(numeric <= value["max"])
            elif isinstance(value, str):
                if key in {"model", "compatible_model"}:
                    normalized = func.regexp_replace(
                        func.lower(column.astext), r"([0-9])\s*\+", r"\1 plus ", "g"
                    )
                    normalized = func.regexp_replace(normalized, r"\ms\s+([0-9]+)", r"s\1", "g")
                    normalized = func.regexp_replace(normalized, r"[^a-z0-9]+", "", "g")
                    stmt = stmt.where(normalized == "".join(search_tokens(value)))
                else:
                    stmt = stmt.where(func.lower(column.astext) == value.casefold())
            else:
                stmt = stmt.where(m.ListingModel.category_data.contains({key: value}))
        if condition is not None:
            stmt = stmt.where(m.ListingModel.condition == condition)
        if min_trust_score is not None:
            # An inner-join-shaped filter via an outer-joined column: a
            # seller with no score row yet (TrustScoreModel.score is NULL)
            # correctly fails every "N+" threshold rather than matching one
            # by SQL NULL-comparison accident.
            stmt = stmt.where(m.TrustScoreModel.score >= min_trust_score)
        if max_trust_score is not None:
            stmt = stmt.where(m.TrustScoreModel.score <= max_trust_score)
        if verified_only:
            stmt = stmt.where(m.SellerProfile.identity_status == e.VerificationStatus.VERIFIED)
        if q:
            # The trigram GIN index on `title` (ix_listings_title_trgm) makes
            # this ILIKE cheap even without a leading anchor.
            normalized_title = func.regexp_replace(
                func.lower(m.ListingModel.title), r"([0-9])\s*\+", r"\1 plus ", "g"
            )
            normalized_title = func.regexp_replace(normalized_title, r"\ms\s+([0-9]+)", r"s\1", "g")
            for token in search_tokens(q):
                # Tokens contain letters/digits only; %/_ are never wildcard input.
                stmt = stmt.where(normalized_title.op("~")(r"\m" + token + r"\M"))
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

    async def category_field_options(
        self,
        node_id: str,
        field: str,
        *,
        parent_key: str | None = None,
        parent_value: str | None = None,
        query: str = "",
    ) -> list[str]:
        # Reuse the public eligibility predicate: private/flagged/unverified ads
        # must not leak even a brand or model through suggestion endpoints.
        facets = {parent_key: parent_value} if parent_key and parent_value else {}
        column = m.ListingModel.category_data[field].astext
        stmt = (
            self._public_query_base(category=None, q=None, category_node_id=node_id, facets=facets)
            .with_only_columns(column)
            .where(column.isnot(None))
        )
        if query.strip():
            stmt = stmt.where(
                column.ilike(
                    "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%",
                    escape="\\",
                )
            )
        rows = (await self._s.execute(stmt.distinct().order_by(column).limit(40))).scalars().all()
        return [value for value in rows if value and len(value) <= 160]

    def _order_by(self, stmt: Select[Any], sort: str, q: str | None = None) -> Select[Any]:
        if sort == "relevance" and q and search_tokens(q):
            # Filtering already requires every literal term. Prefer an exact
            # title, then a concise match; deterministic ties keep paging stable.
            exact = func.lower(m.ListingModel.title) == q.strip().casefold()
            return stmt.order_by(
                case((exact, 0), else_=1),
                func.length(m.ListingModel.title),
                m.ListingModel.created_at.desc(),
                m.ListingModel.id.desc(),
            )
        if sort == "price_asc":
            # NULLS LAST: a listing with no price is not "cheapest".
            return stmt.order_by(
                m.ListingModel.price.is_(None), m.ListingModel.price.asc(), m.ListingModel.id.desc()
            )
        if sort == "price_desc":
            return stmt.order_by(
                m.ListingModel.price.is_(None),
                m.ListingModel.price.desc(),
                m.ListingModel.id.desc(),
            )
        return stmt.order_by(m.ListingModel.created_at.desc(), m.ListingModel.id.desc())

    async def search_public(
        self,
        *,
        category: str | None = None,
        category_node_id: str | None = None,
        facets: dict | None = None,
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
        condition: str | None = None,
        min_trust_score: int | None = None,
        max_trust_score: int | None = None,
        verified_only: bool = False,
        sort: str = "newest",
        limit: int = 20,
        offset: int = 0,
    ) -> list[ent.PublicListingSummary]:
        stmt = self._public_query_base(
            category=category,
            category_node_id=category_node_id,
            facets=facets,
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
            condition=condition,
            min_trust_score=min_trust_score,
            max_trust_score=max_trust_score,
            verified_only=verified_only,
        )
        stmt = self._order_by(stmt, sort, q).limit(limit).offset(offset)
        rows = (await self._s.execute(stmt)).all()
        listing_ids = [listing.id for listing, _seller, _risk, _score in rows]
        primary_images = await _primary_image_ids(self._s, listing_ids)

        return [
            _to_public_summary(listing, seller, risk_level, score, primary_images)
            for listing, seller, risk_level, score in rows
        ]

    async def count_public(
        self,
        *,
        category: str | None = None,
        category_node_id: str | None = None,
        facets: dict | None = None,
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
        condition: str | None = None,
        min_trust_score: int | None = None,
        max_trust_score: int | None = None,
        verified_only: bool = False,
    ) -> int:
        stmt = select(func.count()).select_from(
            self._public_query_base(
                category=category,
                category_node_id=category_node_id,
                facets=facets,
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
                condition=condition,
                min_trust_score=min_trust_score,
                max_trust_score=max_trust_score,
                verified_only=verified_only,
            ).subquery()
        )
        return int((await self._s.execute(stmt)).scalar_one())

    async def public_dealers(
        self, *, limit: int = 12, offset: int = 0, city: str | None = None, q: str | None = None
    ) -> list[dict]:
        # Only approved business profiles with currently eligible motor listings.
        # Reuses every normal profile/photo/listing visibility predicate.
        stmt = (
            self._public_query_base(category="vehicles", q=None)
            .where(
                m.SellerProfile.account_type == e.SellerAccountType.BUSINESS,
                m.SellerProfile.business_verification_status == e.VerificationStatus.VERIFIED,
            )
            .with_only_columns(
                m.SellerProfile.handle.label("handle"),
                m.SellerProfile.display_name.label("display_name"),
                m.SellerProfile.user_id.label("user_id"),
                m.SellerProfile.city.label("city"),
                func.count(m.ListingModel.id).label("active_listings"),
            )
            .group_by(m.SellerProfile.id)
            .order_by(func.count(m.ListingModel.id).desc(), m.SellerProfile.id)
            .limit(max(1, min(limit, 50)))
            .offset(max(0, offset))
        )
        if city:
            stmt = stmt.where(m.SellerProfile.city == city)
        if q:
            pattern = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            stmt = stmt.where(m.SellerProfile.display_name.ilike(pattern, escape="\\"))
        return [dict(row._mapping) for row in (await self._s.execute(stmt)).all()]

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
                m.SellerProfile.identity_status == e.VerificationStatus.VERIFIED,
                m.SellerProfile.phone_status == e.VerificationStatus.VERIFIED,
                m.SellerProfile.email_status == e.VerificationStatus.VERIFIED,
                m.SellerProfile.is_flagged.is_(False),
                photos_cleared(),
                listing_profile_ready(),
                listing_not_paused(),
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
            .where(
                m.ListingImageModel.listing_id == listing_id,
                m.ListingImageModel.is_removed.is_(False),
            )
            .order_by(m.ListingImageModel.position)
        )
        images = tuple(
            ent.PublicListingImage(
                file_id=file_id, is_primary=is_primary, thumbnail_object_key=thumb_key
            )
            for file_id, is_primary, thumb_key in image_rows
        )

        # Explicit per-listing consent; only the current primary verified phone.
        # Private addresses and phone numbers never enter summary/search responses.
        public_phone = None
        if listing.show_phone and seller.phone_status == e.VerificationStatus.VERIFIED:
            public_phone = (
                await self._s.execute(
                    select(m.PhoneNumberModel.e164)
                    .where(
                        m.PhoneNumberModel.user_id == seller.user_id,
                        m.PhoneNumberModel.deleted_at.is_(None),
                        m.PhoneNumberModel.is_primary.is_(True),
                        m.PhoneNumberModel.verified_at.is_not(None),
                    )
                    .order_by(m.PhoneNumberModel.verified_at.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()

        return ent.PublicListingDetail(
            id=listing.id,
            title=listing.title,
            description=listing.description,
            price=float(listing.price) if listing.price is not None else None,
            currency=listing.currency,
            category=listing.category,
            category_node_id=listing.category_node_id,
            category_schema_version=listing.category_schema_version,
            category_data=dict(listing.category_data or {}),
            condition=listing.condition,
            city=listing.city,
            area=listing.area,
            created_at=listing.created_at,
            seller_id=seller.id,
            seller_handle=seller.handle,
            seller_display_name=seller.display_name,
            seller_user_id=seller.user_id,
            status=listing.status.value,
            negotiable=listing.negotiable,
            attributes=dict(listing.attributes or {}),
            show_phone=listing.show_phone,
            public_phone=public_phone,
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
                category_node_id=listing.category_node_id,
                category_schema_version=listing.category_schema_version,
                category_data=dict(listing.category_data or {}),
                condition=listing.condition,
                city=listing.city,
                area=listing.area,
                address_line=listing.address_line,
                latitude=listing.latitude,
                longitude=listing.longitude,
                country_code=listing.country_code,
                external_url=listing.external_url,
                posted_at=listing.posted_at,
                status=listing.status,
                negotiable=listing.negotiable,
                attributes=listing.attributes,
                show_phone=listing.show_phone,
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
                category_node_id=listing.category_node_id,
                category_schema_version=listing.category_schema_version,
                category_data=dict(listing.category_data or {}),
                condition=listing.condition,
                # city/area/lat/lng/country_code were silently dropped here
                # before - the column existed, `add()` wrote it, but `update()`
                # never did, so editing a listing's location did nothing.
                city=listing.city,
                area=listing.area,
                address_line=listing.address_line,
                latitude=listing.latitude,
                longitude=listing.longitude,
                country_code=listing.country_code,
                status=(
                    sql_cast(
                        case(
                            (
                                photos_cleared() & listing_profile_ready() & listing_not_paused(),
                                e.ListingStatus.ACTIVE.value,
                            ),
                            else_=e.ListingStatus.DRAFT.value,
                        ),
                        m.ListingModel.status.type,
                    )
                    if listing.status == e.ListingStatus.ACTIVE
                    else listing.status
                ),
                negotiable=listing.negotiable,
                attributes=listing.attributes,
                show_phone=listing.show_phone,
                video_file_id=listing.video_file_id,
                latest_analysis_id=(
                    listing.latest_analysis.id if listing.latest_analysis else None
                ),
                version=m.ListingModel.version + 1,
            )
        )
        return listing

    async def set_publication_status_if_current(
        self,
        listing_id: UUID,
        *,
        from_status: e.ListingStatus,
        to_status: e.ListingStatus,
        expected_version: int,
        expected_analysis_id: UUID | None,
        at: datetime,
    ) -> bool:
        # A verification callback must not replace the full listing entity:
        # update() would overwrite an edit and could drop latest_analysis_id.
        # Comparing both version and analysis pointer closes that race.
        result = await self._s.execute(
            update(m.ListingModel)
            .where(
                m.ListingModel.id == listing_id,
                m.ListingModel.deleted_at.is_(None),
                m.ListingModel.status == from_status,
                m.ListingModel.version == expected_version,
                m.ListingModel.latest_analysis_id == expected_analysis_id,
                (photos_cleared() & listing_profile_ready() & listing_not_paused())
                if to_status == e.ListingStatus.ACTIVE
                else True,
            )
            .values(
                status=to_status,
                updated_at=at,
                version=m.ListingModel.version + 1,
            )
            .returning(m.ListingModel.id)
        )
        return result.scalar_one_or_none() is not None

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
                    func.percentile_cont(0.5).within_group(
                        m.ListingModel.price.asc(), m.ListingModel.id.desc()
                    ),
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
                thumbnail_object_key=image.thumbnail_object_key,
                created_at=image.created_at,
            )
        )
        await self._s.flush()
        return image

    async def list_images(self, listing_id: UUID) -> list[ent.ListingImage]:
        rows = await self._s.execute(
            select(m.ListingImageModel)
            .where(
                m.ListingImageModel.listing_id == listing_id,
                m.ListingImageModel.is_removed.is_(False),
            )
            .order_by(m.ListingImageModel.position)
        )
        return [map_.to_listing_image(r) for r in rows.scalars().all()]

    async def count_images(self, listing_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count(m.ListingImageModel.id)).where(
                        m.ListingImageModel.listing_id == listing_id,
                        m.ListingImageModel.is_removed.is_(False),
                    )
                )
            ).scalar_one()
        )

    async def lock_owned_for_media(self, listing_id: UUID, seller_id: UUID) -> ent.Listing:
        from trustlens.core.domain.errors import EntityNotFound

        row = (
            await self._s.execute(
                select(m.ListingModel)
                .where(
                    m.ListingModel.id == listing_id,
                    m.ListingModel.seller_id == seller_id,
                    m.ListingModel.deleted_at.is_(None),
                    m.ListingModel.status != e.ListingStatus.REMOVED,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if row is None:
            raise EntityNotFound("listing", listing_id)
        return map_.to_listing(row)

    async def edit_images(
        self,
        listing_id: UUID,
        seller_id: UUID,
        *,
        order: list[UUID] | None = None,
        remove_id: UUID | None = None,
    ) -> None:
        from trustlens.core.domain.errors import EntityNotFound, ValidationError

        listing = (
            await self._s.execute(
                select(m.ListingModel)
                .where(
                    m.ListingModel.id == listing_id,
                    m.ListingModel.seller_id == seller_id,
                    m.ListingModel.deleted_at.is_(None),
                    m.ListingModel.status != e.ListingStatus.REMOVED,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if listing is None:
            raise EntityNotFound("listing", listing_id)
        images = list(
            (
                await self._s.execute(
                    select(m.ListingImageModel)
                    .where(
                        m.ListingImageModel.listing_id == listing_id,
                        m.ListingImageModel.is_removed.is_(False),
                    )
                    .order_by(m.ListingImageModel.position)
                    .with_for_update()
                )
            ).scalars()
        )
        by_id = {image.id: image for image in images}
        if remove_id is not None:
            if remove_id not in by_id:
                raise EntityNotFound("image", remove_id)
            # Retain file and fingerprint evidence: another account still cannot
            # reuse a previously claimed photo after it is hidden from the ad.
            by_id[remove_id].is_removed = True
            by_id[remove_id].is_primary = False
            images = [image for image in images if image.id != remove_id]
        if order is not None:
            if len(order) != len(set(order)) or set(order) != set(by_id):
                raise ValidationError(
                    "Refresh photos and submit every current photo once.", field="imageIds"
                )
            images = [by_id[id] for id in order]
        for position, image in enumerate(images):
            image.position = position
            image.is_primary = position == 0
        listing.version += 1
        if remove_id is not None:
            # A changed photo set must be analysed again before publication.
            listing.status = e.ListingStatus.DRAFT
        await self._s.flush()

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
            m.ListingImageModel.is_removed.is_(False),
        )
    )
    return {listing_id: (file_id, thumb_key) for listing_id, file_id, thumb_key in rows}


def _to_public_summary(
    listing: m.ListingModel,
    seller: m.SellerProfile,
    risk_level: e.RiskLevel | None,
    score: int | None,
    primary_images: dict[UUID, tuple[UUID, str | None]],
) -> ent.PublicListingSummary:
    image = primary_images.get(listing.id)
    return ent.PublicListingSummary(
        id=listing.id,
        title=listing.title,
        price=float(listing.price) if listing.price is not None else None,
        currency=listing.currency,
        category=listing.category,
        category_node_id=listing.category_node_id,
        category_schema_version=listing.category_schema_version,
        category_data=dict(listing.category_data or {}),
        condition=listing.condition,
        city=listing.city,
        area=listing.area,
        created_at=listing.created_at,
        seller_id=seller.id,
        seller_handle=seller.handle,
        seller_display_name=seller.display_name,
        seller_user_id=seller.user_id,
        status=listing.status.value,
        negotiable=listing.negotiable,
        risk_level=risk_level.value if risk_level is not None else None,
        score=score,
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
                m.TrustScoreModel.score,
            )
            .join(m.FavoriteModel, m.FavoriteModel.listing_id == m.ListingModel.id)
            .join(m.SellerProfile, m.SellerProfile.id == m.ListingModel.seller_id)
            .outerjoin(
                m.TrustScoreModel, m.TrustScoreModel.id == m.SellerProfile.current_trust_score_id
            )
            .where(
                m.FavoriteModel.user_id == user_id,
                m.ListingModel.status.in_(
                    [e.ListingStatus.ACTIVE, e.ListingStatus.RESERVED, e.ListingStatus.SOLD]
                ),
                m.ListingModel.deleted_at.is_(None),
                m.SellerProfile.deleted_at.is_(None),
                m.SellerProfile.identity_status == e.VerificationStatus.VERIFIED,
                m.SellerProfile.phone_status == e.VerificationStatus.VERIFIED,
                m.SellerProfile.email_status == e.VerificationStatus.VERIFIED,
                m.SellerProfile.is_flagged.is_(False),
                photos_cleared(),
                listing_profile_ready(),
                listing_not_paused(),
            )
            .order_by(m.FavoriteModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = (await self._s.execute(stmt)).all()
        listing_ids = [listing.id for listing, _seller, _favorited_at, _risk, _score in rows]
        primary_images = await _primary_image_ids(self._s, listing_ids)

        return [
            _to_public_summary(listing, seller, risk_level, score, primary_images)
            for listing, seller, _favorited_at, risk_level, score in rows
        ]

    async def count_for_user(self, user_id: UUID) -> int:
        return int(
            (
                await self._s.execute(
                    select(func.count())
                    .select_from(m.FavoriteModel)
                    .join(m.ListingModel, m.ListingModel.id == m.FavoriteModel.listing_id)
                    .join(m.SellerProfile, m.SellerProfile.id == m.ListingModel.seller_id)
                    .where(
                        m.FavoriteModel.user_id == user_id,
                        m.ListingModel.status.in_(
                            [e.ListingStatus.ACTIVE, e.ListingStatus.RESERVED, e.ListingStatus.SOLD]
                        ),
                        m.ListingModel.deleted_at.is_(None),
                        m.SellerProfile.deleted_at.is_(None),
                        m.SellerProfile.identity_status == e.VerificationStatus.VERIFIED,
                        m.SellerProfile.phone_status == e.VerificationStatus.VERIFIED,
                        m.SellerProfile.email_status == e.VerificationStatus.VERIFIED,
                        m.SellerProfile.is_flagged.is_(False),
                        photos_cleared(),
                        listing_profile_ready(),
                        listing_not_paused(),
                    )
                )
            ).scalar_one()
        )


def _to_saved_search(row: m.SavedSearchModel) -> ent.SavedSearch:
    return ent.SavedSearch(
        id=row.id,
        user_id=row.user_id,
        name=row.name,
        category=row.category,
        category_node_id=row.category_node_id,
        facets=row.facets or {},
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
                category_node_id=search.category_node_id,
                facets=search.facets or {},
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
