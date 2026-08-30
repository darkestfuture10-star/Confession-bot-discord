from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Confession, ModerationLog, Server


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


class ConfessionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

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

    async def review(self, confession_id: int, server_id: int, moderator_id: int, status: str, reason: str | None = None) -> bool:
        """Atomically transition a pending confession, preventing double moderation."""
        result = await self.session.execute(
            update(Confession)
            .where(Confession.id == confession_id, Confession.server_id == server_id, Confession.status == "pending")
            .values(status=status, reviewed_by_id=moderator_id, reviewed_at=datetime.utcnow(), rejection_reason=reason)
        )
        await self.session.commit()
        return result.rowcount == 1

    async def create(self, server_id: int, author_id: int, content: str, status: str, parent_id: int | None = None, reply_number: int | None = None) -> Confession:
        confession = Confession(server_id=server_id, author_id=author_id, content=content, status=status, parent_id=parent_id, reply_number=reply_number)
        self.session.add(confession)
        await self.session.flush()
        await self.session.commit()
        await self.session.refresh(confession)
        return confession

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