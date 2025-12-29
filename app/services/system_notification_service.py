import logging
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.admin import AdminUser
from app.models.notification import NotificationType
from app.models.user import User
from app.services.telegram_notify_service import TelegramNotifyService

logger = logging.getLogger(__name__)


class SystemNotificationService:
    """Handles system-wide notifications such as admin alerts."""

    def __init__(
        self,
        session: AsyncSession | None = None,
        telegram_service: TelegramNotifyService | None = None,
    ) -> None:
        self.session = session
        self.telegram = telegram_service or TelegramNotifyService()

    async def _get_admin_ids(self) -> list[int]:
        """Return list of admin telegram IDs from DB or settings."""

        if self.session is not None:
            stmt = (
                select(User.telegram_id)
                .join(AdminUser, AdminUser.user_id == User.id)
                .where(
                    AdminUser.active.is_(True),
                    User.telegram_id.is_not(None),
                )
            )
            result = await self.session.execute(stmt)
            rows: Iterable[tuple[int]] = result.all()
            admin_ids = [row[0] for row in rows if row[0]]
            if admin_ids:
                return admin_ids

        return [admin for admin in settings.TELEGRAM_ADMIN_IDS if admin]

    async def notify_admins(
        self,
        message_type: NotificationType,
        payload: dict[str, Any],
        *,
        language: str = "ru",
    ) -> None:
        """Send an alert message to configured administrators."""

        admin_ids = await self._get_admin_ids()

        if not admin_ids:
            logger.warning("Admin notification skipped: no admin recipients configured")
            return

        message = {
            "type": message_type.value,
            "language": language,
            "data": payload,
        }

        for admin_id in admin_ids:
            success = await self.telegram.send_message(admin_id, message)
            if not success:
                logger.error(
                    "Failed to deliver admin notification to telegram_id=%s",
                    admin_id,
                )
