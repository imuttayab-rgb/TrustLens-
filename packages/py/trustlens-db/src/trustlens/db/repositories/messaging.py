"""Messaging repositories. Preserve table names and transaction behavior across imports."""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from trustlens.core.domain import entities as ent
from trustlens.db import models as m


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

    def _conversation_filters(self, stmt, user_id, folder="all", query=""):
        from trustlens.db.profiles import name_verified

        c = m.ConversationModel
        if folder == "buying":
            stmt = stmt.where(c.buyer_id == user_id)
        elif folder == "selling":
            stmt = stmt.where(m.SellerProfile.user_id == user_id)
        elif folder == "unread":
            stmt = stmt.where(
                select(m.MessageModel.id)
                .where(
                    m.MessageModel.conversation_id == c.id,
                    m.MessageModel.sender_id != user_id,
                    m.MessageModel.read_at.is_(None),
                    self._visible_chat(user_id),
                )
                .exists()
            )
        elif folder == "important":
            stmt = stmt.where(
                select(m.ConversationPreferenceModel.conversation_id)
                .where(
                    m.ConversationPreferenceModel.conversation_id == c.id,
                    m.ConversationPreferenceModel.user_id == user_id,
                    m.ConversationPreferenceModel.important.is_(True),
                )
                .exists()
            )
        if query.strip():
            pattern = (
                "%"
                + query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                + "%"
            )
            counterpart = case((c.buyer_id == user_id, m.SellerProfile.user_id), else_=c.buyer_id)
            public_name = (
                select(m.AccountProfileModel.user_id)
                .where(
                    m.AccountProfileModel.user_id == counterpart,
                    name_verified(m.AccountProfileModel.user_id),
                    m.AccountProfileModel.public_name.ilike(pattern, escape="\\"),
                )
                .exists()
            )
            stmt = stmt.where(
                or_(c.listing_title_snapshot.ilike(pattern, escape="\\"), public_name)
            )
        return stmt

    async def list_conversations_for_user(
        self,
        user_id: UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        folder: str = "all",
        query: str = "",
    ) -> list[ent.ConversationSummary]:
        stmt = (
            select(
                m.ConversationModel,
                m.SellerProfile,
                m.User,
                m.ListingModel,
                m.TrustScoreModel.risk_level,
                m.TrustScoreModel.score,
            )
            .join(m.SellerProfile, m.SellerProfile.id == m.ConversationModel.seller_id)
            .join(m.User, m.User.id == m.ConversationModel.buyer_id)
            .outerjoin(m.ListingModel, m.ListingModel.id == m.ConversationModel.listing_id)
            .outerjoin(
                m.TrustScoreModel, m.TrustScoreModel.id == m.SellerProfile.current_trust_score_id
            )
            .where((m.ConversationModel.buyer_id == user_id) | (m.SellerProfile.user_id == user_id))
            .order_by(m.ConversationModel.last_message_at.desc())
            .limit(limit)
            .offset(offset)
        )
        stmt = self._conversation_filters(stmt, user_id, folder, query)
        rows = (await self._s.execute(stmt)).all()
        conversation_ids = [c.id for c, _seller, _buyer, _listing, _risk, _score in rows]
        previews = await self._previews(conversation_ids, user_id)
        unread = await self._unread_counts(conversation_ids, reader_id=user_id)

        summaries = []
        for conversation, seller, buyer, listing, risk_level, score in rows:
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
                    counterpart_seller_handle=seller.handle if not is_seller_side else None,
                    counterpart_risk_level=(
                        risk_level.value if not is_seller_side and risk_level is not None else None
                    ),
                    counterpart_score=score if not is_seller_side else None,
                )
            )
        return summaries

    def _visible_chat(self, user_id):
        cutoff = (
            select(m.ChatClearModel.cleared_before)
            .where(
                m.ChatClearModel.user_id == user_id,
                m.ChatClearModel.conversation_id == m.MessageModel.conversation_id,
            )
            .correlate(m.MessageModel)
            .scalar_subquery()
        )
        return or_(cutoff.is_(None), m.MessageModel.created_at > cutoff)

    async def _previews(self, conversation_ids: list[UUID], user_id: UUID) -> dict[UUID, str]:
        if not conversation_ids:
            return {}
        visible_body = case(
            (m.MessageModel.moderated_at.is_not(None), "Message hidden by support"),
            (m.MessageModel.deleted_for_everyone_at.is_not(None), "This message was deleted"),
            else_=func.coalesce(m.MessageModel.edited_body, m.MessageModel.body),
        )
        ranked = (
            select(
                m.MessageModel.conversation_id,
                visible_body.label("preview"),
                func.row_number()
                .over(
                    partition_by=m.MessageModel.conversation_id,
                    order_by=(m.MessageModel.created_at.desc(), m.MessageModel.id.desc()),
                )
                .label("position"),
            )
            .where(
                m.MessageModel.conversation_id.in_(conversation_ids), self._visible_chat(user_id)
            )
            .subquery()
        )
        stmt = select(ranked.c.conversation_id, ranked.c.preview).where(ranked.c.position == 1)
        return dict((await self._s.execute(stmt)).all())

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
                self._visible_chat(reader_id),
            )
            .group_by(m.MessageModel.conversation_id)
        )
        rows = await self._s.execute(stmt)
        return dict(rows.all())

    async def count_conversations_for_user(
        self, user_id: UUID, *, folder: str = "all", query: str = ""
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(m.ConversationModel)
            .join(m.SellerProfile, m.SellerProfile.id == m.ConversationModel.seller_id)
            .where((m.ConversationModel.buyer_id == user_id) | (m.SellerProfile.user_id == user_id))
        )
        return int(
            (
                await self._s.execute(self._conversation_filters(stmt, user_id, folder, query))
            ).scalar_one()
        )

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
