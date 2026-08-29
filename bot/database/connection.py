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
    """Create tables and safely upgrade schemas created by earlier phases."""

    from bot.database import models

    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all
        )

        await connection.execute(
            text(
                """
                ALTER TABLE servers
                ADD COLUMN IF NOT EXISTS approval_enabled
                BOOLEAN NOT NULL DEFAULT TRUE
                """
            )
        )

        # ``create_all`` intentionally does not alter existing PostgreSQL tables.
        # These additive migrations preserve submissions made with earlier builds.
        await connection.execute(
            text(
                """
                ALTER TABLE confessions
                ADD COLUMN IF NOT EXISTS user_id BIGINT,
                ADD COLUMN IF NOT EXISTS content TEXT,
                ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'pending',
                ADD COLUMN IF NOT EXISTS submitted_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
                ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITHOUT TIME ZONE,
                ADD COLUMN IF NOT EXISTS reviewed_by_id BIGINT,
                ADD COLUMN IF NOT EXISTS rejection_reason TEXT,
                ADD COLUMN IF NOT EXISTS public_message_id BIGINT
                """
            )
        )
        await connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_confessions_server_id ON confessions (server_id)")
        )
        await connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_confessions_user_id ON confessions (user_id)")
        )
        await connection.execute(
            text("CREATE INDEX IF NOT EXISTS ix_confessions_status ON confessions (status)")
        )

        # Earlier builds of this bot used a different confessions schema (e.g. an
        # "approved" boolean column). ``create_all``/``ADD COLUMN`` never drops or
        # relaxes old columns, so any leftover NOT NULL column with no default
        # blocks every insert. Auto-heal by dropping NOT NULL from anything the
        # current model doesn't know about.
        current_model_columns = {
            "id",
            "server_id",
            "user_id",
            "content",
            "status",
            "submitted_at",
            "reviewed_at",
            "reviewed_by_id",
            "rejection_reason",
            "public_message_id",
        }

        result = await connection.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'confessions'
                  AND is_nullable = 'NO'
                  AND column_default IS NULL
                """
            )
        )
        legacy_not_null_columns = {row[0] for row in result} - current_model_columns

        for column_name in legacy_not_null_columns:
            await connection.execute(
                text(f'ALTER TABLE confessions ALTER COLUMN "{column_name}" DROP NOT NULL')
            )


def get_session() -> AsyncSession:
    """Create a new database session."""

    return AsyncSessionLocal()


async def close_database():
    """Dispose of the database engine."""

    await engine.dispose()
