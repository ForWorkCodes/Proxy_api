import logging
from typing import Any

from app.core.config import settings
from app.models.notification import NotificationType
from app.services.telegram_notify_service import TelegramNotifyService

logger = logging.getLogger(__name__)


class SystemNotificationService:
    """Handles system-wide notifications such as admin alerts."""

    def __init__(
        self,
        telegram_service: TelegramNotifyService | None = None,
    ) -> None:
        self.telegram = telegram_service or TelegramNotifyService()
        self._admin_ids = [admin for admin in settings.TELEGRAM_ADMIN_IDS if admin]

    async def notify_admins(
        self,
        message_type: NotificationType,
        payload: dict[str, Any],
        *,
        language: str = "ru",
    ) -> None:
        """Send an alert message to configured administrators."""

        if not self._admin_ids:
            logger.warning("Admin notification skipped: TELEGRAM_ADMIN_IDS is empty")
            return

        message = {
            "type": message_type.value,
            "language": language,
            "data": payload,
        }

        for admin_id in self._admin_ids:
            success = await self.telegram.send_message(admin_id, message)
            if not success:
                logger.error(
                    "Failed to deliver admin notification to telegram_id=%s",
                    admin_id,
                )
