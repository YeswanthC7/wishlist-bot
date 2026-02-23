# db/models.py
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ChannelConfig(Base):
    __tablename__ = "channel_config"

    guild_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        Index("ix_channel_config_guild_channel", "guild_id", "channel_id"),
    )


class WishlistItem(Base):
    __tablename__ = "wishlist_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    guild_id: Mapped[str] = mapped_column(String(32), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(32), nullable=False)

    url: Mapped[str] = mapped_column(Text, nullable=False)
    url_norm: Mapped[str] = mapped_column(Text, nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[str] = mapped_column(Text, nullable=True)

    user_tag: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("channel_id", "url_norm", name="uq_wishlist_channel_urlnorm"),
        Index("ix_wishlist_guild_channel_created", "guild_id", "channel_id", "created_at"),
    )
