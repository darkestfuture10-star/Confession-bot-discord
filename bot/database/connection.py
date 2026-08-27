from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from bot.config.settings import DATABASE_URL


# Database

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def test_database_connection():
    """Check that PostgreSQL is reachable."""

    async with engine.connect() as connection:
        await connection.run_sync(lambda _: None)


async def initialize_database():
    """Create database tables that do not already exist."""

    from bot.database import models

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )

        #temp test
        await connection.execute(
            text(
                """
                ALTER TABLE servers
                ADD COLUMN IF NOT EXISTS approval_enabled
                BOOLEAN NOT NULL DEFAULT TRUE
                """
            )
        )
        #temp test


def get_session() -> AsyncSession:
    """Create a new database session."""

    return AsyncSessionLocal()


async def close_database():
    """Dispose of the database engine."""

    await engine.dispose()