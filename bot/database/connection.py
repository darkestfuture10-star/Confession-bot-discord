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


# Every column the current models actually declare, per table. Used to
# auto-heal tables that predate the current schema (older builds of this
# bot used different column sets) — anything NOT NULL with no default that
# isn't in this list gets relaxed, since a leftover mandatory column with
# no way to populate it blocks every INSERT.
CURRENT_MODEL_COLUMNS = {
    "servers": {
        "id",
        "confession_channel_id",
        "moderator_role_id",
        "approval_enabled",
        "logging_enabled",
        "logging_channel_id",
        "last_confession_message_id",
        "theme",
        "next_reply_number",
        "sensitive_content_detection",
    },
    "confessions": {
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
        "parent_id",
        "reply_number",
    },
}


async def _heal_legacy_not_null_columns(connection) -> None:
    for table_name, known_columns in CURRENT_MODEL_COLUMNS.items():
        result = await connection.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = :table_name
                  AND is_nullable = 'NO'
                  AND column_default IS NULL
                """
            ),
            {"table_name": table_name},
        )
        legacy_not_null_columns = {row[0] for row in result} - known_columns

        for column_name in legacy_not_null_columns:
            await connection.execute(
                text(f'ALTER TABLE {table_name} ALTER COLUMN "{column_name}" DROP NOT NULL')
            )


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

        await connection.execute(
            text(
                """
                ALTER TABLE servers
                ADD COLUMN IF NOT EXISTS last_confession_message_id BIGINT
                """
            )
        )

        await connection.execute(
            text(
                """
                ALTER TABLE servers
                ADD COLUMN IF NOT EXISTS theme VARCHAR(50) NOT NULL DEFAULT 'default'
                """
            )
        )

        await connection.execute(
            text(
                """
                ALTER TABLE servers
                ADD COLUMN IF NOT EXISTS next_reply_number BIGINT NOT NULL DEFAULT 1
                """
            )
        )

        await connection.execute(
            text(
                """
                ALTER TABLE servers
                ADD COLUMN IF NOT EXISTS sensitive_content_detection BOOLEAN NOT NULL DEFAULT FALSE
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
                ADD COLUMN IF NOT EXISTS public_message_id BIGINT,
                ADD COLUMN IF NOT EXISTS parent_id BIGINT,
                ADD COLUMN IF NOT EXISTS reply_number BIGINT
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

        # Earlier builds of this bot used different schemas for both tables
        # (e.g. an "approved" boolean on confessions, a "created_at" column
        # on servers). Auto-heal any leftover mandatory columns that aren't
        # part of the current models, on every table we know about.
        await _heal_legacy_not_null_columns(connection)


def get_session() -> AsyncSession:
    """Create a new database session."""

    return AsyncSessionLocal()


async def close_database():
    """Dispose of the database engine."""

    await engine.dispose()