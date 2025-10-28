from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Text
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.core.sync_db import Base
from datetime import datetime
import enum


class NotificationType(str, enum.Enum):
    proxy_expiring = "proxy_expiring"
    proxy_auto_prolong_success = "proxy_auto_prolong_success"
    proxy_auto_prolong_failed = "proxy_auto_prolong_failed"
    balance_low = "balance_low"
    admin_alert = "admin_alert"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    owner: Mapped["User"] = relationship("User", back_populates="notifications", lazy="selectin")
    type = Column(Enum(NotificationType), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    sent = Column(Boolean, default=False)
    sent_at = Column(DateTime, nullable=True)
    payload = Column(Text)  # JSON-строка с параметрами (например, proxy_id)
