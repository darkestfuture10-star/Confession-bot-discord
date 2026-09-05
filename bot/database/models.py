from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from bot.database.connection import Base


class Server(Base):
    __tablename__ = "servers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    confession_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    moderator_role_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    approval_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    logging_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
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

    theme: Mapped[str] = mapped_column(String(50), default="default", nullable=False)

    # Independent counter for the "Anonymous Reply #N" numbering shown
    # publicly on replies, kept separate from the main confession sequence.
    next_reply_number: Mapped[int] = mapped_column(
        BigInteger,
        default=1,
        nullable=False,
    )

    # When on, confessions matching a short list of crisis/self-harm-related
    # keywords get a quiet heads-up note added to the moderator review embed.
    # Off by default — each server opts in via /config.
    sensitive_content_detection: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Confession(Base):
    __tablename__ = "confessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    server_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("servers.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
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
    # The public-facing reply number (only set when parent_id is set).
    reply_number: Mapped[int | None] = mapped_column(BigInteger, nullable=True)


class ModerationLog(Base):
    __tablename__ = "moderation_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    confession_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("confessions.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
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