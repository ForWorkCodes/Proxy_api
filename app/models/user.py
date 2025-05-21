from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy import String, Integer, Boolean, DateTime
from datetime import datetime, timezone
from app.core.sync_db import Base
from sqlalchemy.orm import relationship
from typing import List, Optional

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    telegram_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    chat_id: Mapped[str] = mapped_column(String, nullable=True)
    username: Mapped[str] = mapped_column(String, nullable=True)
    firstname: Mapped[str] = mapped_column(String, nullable=True)
    language: Mapped[str] = mapped_column(String(5))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    banned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc)
        )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        onupdate=datetime.now(timezone.utc)
        )
    proxies: Mapped[List["Proxy"]] = relationship(
        "Proxy", back_populates="owner", lazy="selectin"
        )
    balance: Mapped[Optional["Balance"]] = relationship(
        "Balance", back_populates="owner", uselist=False, cascade="all, delete-orphan", lazy="selectin"
        )
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="owner", lazy="selectin"
        )