from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    """Base class for database repositories."""

    def __init__(self, session: AsyncSession):
        self.session = session