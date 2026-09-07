from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Confession, ModerationLog, Server, UserRestriction


class ServerRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, server_id: int) -> Server | None:
        result = await self.session.execute(
            select(Server).where(Server.id == server_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, server_id: int) -> Server:
        server = await self.get(server_id)
        if server is None:
            server = Server(id=server_id)
            self.session.add(server)
            await self.session.flush()
        return server

    async def set_confession_channel(self, server_id: int, channel_id: int) -> Server:
        server = await self.get_or_create(server_id)
        server.confession_channel_id = channel_id
        await self.session.commit()
        await self.session.refresh(server)
        return server

    async def set_moderator_role(self, server_id: int, role_id: int) -> Server:
        server = await self.get_or_create(server_id)
        server.moderator_role_id = role_id
        await self.session.commit()
        await self.session.refresh(server)
        return server

    async def set_approval(self, server_id: int, enabled: bool) -> Server:
        server = await self.get_or_create(server_id)
        server.approval_enabled = enabled
        await self.session.commit()
        await self.session.refresh(server)
        return server

    async def set_logging(self, server_id: int, enabled: bool) -> Server:
        server = await self.get_or_create(server_id)
        server.logging_enabled = enabled
        await self.session.commit()
        await self.session.refresh(server)
        return server

    async def set_logging_channel(self, server_id: int, channel_id: int) -> Server:
        server = await self.get_or_create(server_id)
        server.logging_channel_id = channel_id
        await self.session.commit()
        await self.session.refresh(server)
        return server

    async def allocate_reply_number(self, server_id: int) -> int:
        """Atomically claim the next sequential public reply number."""
        result = await self.session.execute(
            update(Server)
            .where(Server.id == server_id)
            .values(next_reply_number=Server.next_reply_number + 1)
            .returning(Server.next_reply_number)
        )
        await self.session.commit()
        new_value = result.scalar_one()
        return new_value - 1

    async def set_theme(self, server_id: int, theme: str) -> Server:
        server = await self.get_or_create(server_id)
        server.theme = theme
        await self.session.commit()
        await self.session.refresh(server)
        return server

    async def set_last_confession_message(self, server_id: int, message_id: int | None) -> None:
        await self.session.execute(
            update(Server).where(Server.id == server_id).values(last_confession_message_id=message_id)
        )
        await self.session.commit()

    async def clear_last_confession_message_if_matches(self, server_id: int, message_id: int) -> None:
        """Used when the tracked 'last confession message' is found to have
        been deleted outside the bot, so we don't keep pointing at a dead
        message for the Submit-button-demotion logic."""
        await self.session.execute(
            update(Server)
            .where(Server.id == server_id, Server.last_confession_message_id == message_id)
            .values(last_confession_message_id=None)
        )
        await self.session.commit()

    async def set_sensitive_detection(self, server_id: int, enabled: bool) -> Server:
        server = await self.get_or_create(server_id)
        server.sensitive_content_detection = enabled
        await self.session.commit()
        await self.session.refresh(server)
        return server


class ConfessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, server_id: int, author_id: int, content: str, status: str, parent_id: int | None = None, reply_number: int | None = None) -> Confession:
        confession = Confession(server_id=server_id, author_id=author_id, content=content, status=status, parent_id=parent_id, reply_number=reply_number)
        self.session.add(confession)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(confession)
        return confession

    async def get(self, confession_id: int, server_id: int) -> Confession | None:
        result = await self.session.execute(
            select(Confession).where(Confession.id == confession_id, Confession.server_id == server_id)
        )
        return result.scalar_one_or_none()

    async def get_for_author(self, confession_id: int, server_id: int, author_id: int) -> Confession | None:
        result = await self.session.execute(
            select(Confession).where(
                Confession.id == confession_id,
                Confession.server_id == server_id,
                Confession.author_id == author_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_public_message(self, server_id: int, message_id: int) -> Confession | None:
        result = await self.session.execute(
            select(Confession).where(Confession.server_id == server_id, Confession.public_message_id == message_id)
        )
        return result.scalar_one_or_none()

    async def review(self, confession_id: int, server_id: int, moderator_id: int, status: str, reason: str | None = None) -> bool:
        """Atomically transition a pending confession, preventing double moderation."""
        result = await self.session.execute(
            update(Confession)
            .where(Confession.id == confession_id, Confession.server_id == server_id, Confession.status == "pending")
            .values(status=status, reviewed_by_id=moderator_id, reviewed_at=datetime.utcnow(), rejection_reason=reason)
        )
        await self.session.commit()
        return result.rowcount == 1

    async def set_public_message(self, confession_id: int, message_id: int) -> None:
        await self.session.execute(
            update(Confession).where(Confession.id == confession_id).values(public_message_id=message_id)
        )
        await self.session.commit()

    async def set_status(self, confession_id: int, status: str) -> None:
        await self.session.execute(
            update(Confession).where(Confession.id == confession_id).values(status=status)
        )
        await self.session.commit()

    async def add_log(self, confession_id: int, action: str, actor_id: int | None = None, details: str | None = None) -> None:
        self.session.add(ModerationLog(confession_id=confession_id, action=action, actor_id=actor_id, details=details))
        await self.session.commit()

    async def list_pending(self, server_id: int, limit: int = 25) -> list[Confession]:
        """Oldest-first queue of confessions awaiting moderator review."""
        result = await self.session.execute(
            select(Confession)
            .where(Confession.server_id == server_id, Confession.status == "pending")
            .order_by(Confession.submitted_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_logs(self, confession_id: int) -> list[ModerationLog]:
        """Full audit trail for a single confession, oldest first."""
        result = await self.session.execute(
            select(ModerationLog)
            .where(ModerationLog.confession_id == confession_id)
            .order_by(ModerationLog.created_at.asc())
        )
        return list(result.scalars().all())

    async def count_by_status(self, server_id: int) -> dict[str, int]:
        result = await self.session.execute(
            select(Confession.status, func.count())
            .where(Confession.server_id == server_id)
            .group_by(Confession.status)
        )
        return {status: count for status, count in result.all()}

    async def count_pending(self, server_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Confession).where(
                Confession.server_id == server_id, Confession.status == "pending"
            )
        )
        return result.scalar_one()

    async def count_confessions_and_replies(self, server_id: int) -> tuple[int, int]:
        result = await self.session.execute(
            select(func.count()).select_from(Confession).where(
                Confession.server_id == server_id, Confession.parent_id.is_(None)
            )
        )
        confessions = result.scalar_one()
        result = await self.session.execute(
            select(func.count()).select_from(Confession).where(
                Confession.server_id == server_id, Confession.parent_id.is_not(None)
            )
        )
        replies = result.scalar_one()
        return confessions, replies

    async def count_since(self, server_id: int, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Confession).where(
                Confession.server_id == server_id, Confession.submitted_at >= since
            )
        )
        return result.scalar_one()

    async def get_last_submission_time(self, server_id: int, author_id: int) -> datetime | None:
        result = await self.session.execute(
            select(Confession.submitted_at)
            .where(Confession.server_id == server_id, Confession.author_id == author_id)
            .order_by(Confession.submitted_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_last_content_by_author(self, server_id: int, author_id: int) -> str | None:
        result = await self.session.execute(
            select(Confession.content)
            .where(Confession.server_id == server_id, Confession.author_id == author_id)
            .order_by(Confession.submitted_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_recent_by_author(self, server_id: int, author_id: int, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Confession).where(
                Confession.server_id == server_id,
                Confession.author_id == author_id,
                Confession.submitted_at >= since,
            )
        )
        return result.scalar_one()

    async def moderator_stats(self, server_id: int) -> dict[int, dict[str, int]]:
        """Per-moderator counts of approve/reject/delete actions for this server."""
        result = await self.session.execute(
            select(ModerationLog.actor_id, ModerationLog.action, func.count())
            .join(Confession, Confession.id == ModerationLog.confession_id)
            .where(
                Confession.server_id == server_id,
                ModerationLog.action.in_(["approved", "rejected", "deleted"]),
                ModerationLog.actor_id.is_not(None),
            )
            .group_by(ModerationLog.actor_id, ModerationLog.action)
        )
        stats: dict[int, dict[str, int]] = {}
        for actor_id, action, count in result.all():
            stats.setdefault(actor_id, {"approved": 0, "rejected": 0, "deleted": 0})[action] = count
        return stats


class RestrictionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, server_id: int, user_id: int, moderator_id: int, reason: str | None, expires_at: datetime | None) -> UserRestriction:
        # Replace any existing active restriction rather than stacking them.
        await self.lift(server_id, user_id, moderator_id)
        restriction = UserRestriction(
            server_id=server_id, user_id=user_id, moderator_id=moderator_id,
            reason=reason, expires_at=expires_at,
        )
        self.session.add(restriction)
        await self.session.commit()
        await self.session.refresh(restriction)
        return restriction

    async def get_active(self, server_id: int, user_id: int) -> UserRestriction | None:
        result = await self.session.execute(
            select(UserRestriction)
            .where(
                UserRestriction.server_id == server_id,
                UserRestriction.user_id == user_id,
                UserRestriction.active == True,  # noqa: E712
                or_(UserRestriction.expires_at.is_(None), UserRestriction.expires_at > datetime.utcnow()),
            )
            .order_by(UserRestriction.created_at.desc())
        )
        return result.scalars().first()

    async def lift(self, server_id: int, user_id: int, moderator_id: int) -> bool:
        result = await self.session.execute(
            update(UserRestriction)
            .where(
                UserRestriction.server_id == server_id,
                UserRestriction.user_id == user_id,
                UserRestriction.active == True,  # noqa: E712
            )
            .values(active=False, lifted_at=datetime.utcnow(), lifted_by_id=moderator_id)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def list_active(self, server_id: int, limit: int = 25) -> list[UserRestriction]:
        result = await self.session.execute(
            select(UserRestriction)
            .where(
                UserRestriction.server_id == server_id,
                UserRestriction.active == True,  # noqa: E712
                or_(UserRestriction.expires_at.is_(None), UserRestriction.expires_at > datetime.utcnow()),
            )
            .order_by(UserRestriction.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_active(self, server_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(UserRestriction).where(
                UserRestriction.server_id == server_id,
                UserRestriction.active == True,  # noqa: E712
                or_(UserRestriction.expires_at.is_(None), UserRestriction.expires_at > datetime.utcnow()),
            )
        )
        return result.scalar_one()