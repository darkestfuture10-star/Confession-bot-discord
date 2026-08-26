from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String
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