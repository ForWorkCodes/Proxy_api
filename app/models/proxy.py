from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from datetime import datetime, timezone
from app.core.sync_db import Base
from sqlalchemy.orm import relationship

class Proxy(Base):
    __tablename__ = "proxy"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    owner: Mapped["User"] = relationship("User", back_populates="proxies", lazy="selectin")
    proxy_id: Mapped[str] = mapped_column(String, nullable=False)
    ip: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=True)
    transaction_id: Mapped[int] = mapped_column(Integer, nullable=False)
    host: Mapped[str] = mapped_column(String, nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False) #http/https/socks5
    country: Mapped[str] = mapped_column(String, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now(timezone.utc))
    date_end: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    unixtime: Mapped[int] = mapped_column(Integer, nullable=True)
    unixtime_end: Mapped[int] = mapped_column(Integer, nullable=True)
    descr: Mapped[str] = mapped_column(String, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
