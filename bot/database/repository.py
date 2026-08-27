from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Server


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

    async def set_confession_channel(
        self,
        server_id: int,
        channel_id: int,
    ) -> Server:
        server = await self.get_or_create(server_id)

        server.confession_channel_id = channel_id

        await self.session.commit()
        await self.session.refresh(server)

        return server

    async def set_moderator_role(
        self,
        server_id: int,
        role_id: int,
    ) -> Server:
        server = await self.get_or_create(server_id)

        server.moderator_role_id = role_id

        await self.session.commit()
        await self.session.refresh(server)

        return server

    async def set_approval(
            self,
            server_id: int,
            enabled: bool,
    ) -> Server:
        server = await self.get_or_create(server_id)

        server.approval_enabled = enabled

        await self.session.commit()
        await self.session.refresh(server)

        return server

    async def set_logging(
            self,
            server_id: int,
            enabled: bool,
    ) -> Server:
        server = await self.get_or_create(server_id)

        server.logging_enabled = enabled

        await self.session.commit()
        await self.session.refresh(server)

        return server

    async def set_logging_channel(
            self,
            server_id: int,
            channel_id: int,
    ) -> Server:
        server = await self.get_or_create(server_id)

        server.logging_channel_id = channel_id

        await self.session.commit()
        await self.session.refresh(server)

        return server