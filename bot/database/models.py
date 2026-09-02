from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.connection import Base


class Server(Base):
    """Discord server configuration."""

    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
    )

    confession_channel_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    moderator_role_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    approval_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    logging_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    logging_channel_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    # The most recently posted public confession message in the confession
    # channel. Tracked so only that single message keeps the quick "Submit a
    # Confession" button once a newer confession is posted.
    last_confession_message_id: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    next_reply_number: Mapped[int] = mapped_column(
        BigInteger,
        default=1,
        nullable=False,
    )

    theme: Mapped[str] = mapped_column(
        String(50),
        default="default",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class Confession(Base):
    """A submitted confession. The author ID is never used in public output."""

    __tablename__ = "confessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), index=True
    )
    # Keep the existing database column name while using clearer application wording.
    author_id: Mapped[int] = mapped_column("user_id", BigInteger, nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    public_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Set when this confession is a reply to another confession. No DB-level
    # foreign key constraint, matching the informal style of the other
    # migration-added columns above.
    parent_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reply_number: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ModerationLog(Base):
    """Immutable record of a confession lifecycle event."""

    __tablename__ = "moderation_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    confession_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("confessions.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class UserRestriction(Base):
    """A block on a user submitting confessions, temporary or permanent."""

    __tablename__ = "user_restrictions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    moderator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    # None = permanent restriction.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lifted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lifted_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ConfessionReport(Base):
    """A user report against a public confession or reply."""

    __tablename__ = "confession_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    confession_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("confessions.id", ondelete="CASCADE"), index=True
    )
    server_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    reporter_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolved_by_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    resolution: Mapped[str | None] = mapped_column(String(30), nullable=True)
