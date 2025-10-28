import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.services.telegram_notify_service import TelegramNotifyService
from app.services.user_service import UserService

logger = logging.getLogger(__name__)


class NotificationService:
    """Schedules and delivers notifications to Telegram users."""

    def __init__(
        self,
        session: AsyncSession,
        telegram_service: TelegramNotifyService | None = None,
    ) -> None:
        self.session = session
        self.telegram = telegram_service or TelegramNotifyService()
        self.user_service = UserService(session)

    async def process_pending(self, limit: int | None = None) -> int:
        """Deliver notifications scheduled for the current moment.

        Returns
        -------
        int
            Number of notifications successfully delivered to end users.
        """

        now = self._current_time()
        stmt = (
            select(Notification)
            .options(selectinload(Notification.owner))
            .where(
                Notification.scheduled_at <= now,
                Notification.sent.is_(False),
            )
            .order_by(Notification.scheduled_at, Notification.id)
        )

        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self.session.execute(stmt)
        notifications = result.scalars().all()

        delivered = 0

        for notification in notifications:
            user = await self._resolve_user(notification)

            if not user:
                logger.warning(
                    "Skip notification %s because user_id=%s not found",
                    notification.id,
                    notification.user_id,
                )
                self._mark_as_sent(notification, now)
                continue

            if not user.notification:
                logger.info(
                    "Notification %s ignored because user_id=%s disabled notifications",
                    notification.id,
                    notification.user_id,
                )
                self._mark_as_sent(notification, now)
                continue

            if not user.telegram_id:
                logger.warning(
                    "Notification %s skipped because user_id=%s has no telegram_id",
                    notification.id,
                    notification.user_id,
                )
                self._mark_as_sent(notification, now)
                continue

            message_payload = self._build_message_payload(notification, user)

            try:
                send_result = await self.telegram.send_message(
                    user.telegram_id,
                    message_payload,
                )
            except Exception:
                logger.exception(
                    "Unexpected error while sending notification %s to user_id=%s",
                    notification.id,
                    notification.user_id,
                )
                continue

            if send_result:
                delivered += 1
                self._mark_as_sent(notification, now)
            else:
                logger.error(
                    "Telegram gateway rejected notification %s for user_id=%s",
                    notification.id,
                    notification.user_id,
                )

        if notifications:
            await self.session.commit()

        return delivered

    async def schedule_notification(
        self,
        user_id: int,
        note_type: NotificationType,
        when: datetime,
        payload: dict[str, Any] | None = None,
        *,
        deduplicate: bool = False,
    ) -> Notification | None:
        """Persist notification for future delivery.

        When ``deduplicate`` is enabled the method will avoid creating another
        pending notification with the same ``user_id``, ``note_type`` and
        payload.
        """

        scheduled_at = self._normalize_schedule_time(when)
        payload_json = self._serialize_payload(payload)

        if deduplicate:
            exists_stmt = (
                select(Notification.id)
                .where(
                    Notification.user_id == user_id,
                    Notification.type == note_type,
                    Notification.sent.is_(False),
                    Notification.payload == payload_json,
                )
                .limit(1)
            )
            existing = await self.session.execute(exists_stmt)
            if existing.scalar_one_or_none():
                logger.debug(
                    "Skip scheduling duplicate notification for user_id=%s type=%s",
                    user_id,
                    note_type.value,
                )
                return None

        notification = Notification(
            user_id=user_id,
            type=note_type,
            scheduled_at=scheduled_at,
            payload=payload_json,
            sent=False,
        )

        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)

        logger.debug(
            "Scheduled notification id=%s for user_id=%s type=%s at %s",
            notification.id,
            user_id,
            note_type.value,
            scheduled_at.isoformat(),
        )

        return notification

    async def _resolve_user(self, notification: Notification) -> User | None:
        if notification.owner is not None:
            return notification.owner
        return await self.user_service.get_user_by_id(notification.user_id)

    def _build_message_payload(self, notification: Notification, user: User) -> dict[str, Any]:
        payload_data = json.loads(notification.payload or "{}")
        language = user.language or "ru"

        message: dict[str, Any] = {
            "type": notification.type.value,
            "language": language,
        }

        # Ensure system controlled fields cannot be overridden by payload data.
        for key in ("type", "language"):
            payload_data.pop(key, None)

        message.update(payload_data)

        return message

    def _mark_as_sent(self, notification: Notification, now: datetime) -> None:
        notification.sent = True
        notification.sent_at = now
        self.session.add(notification)

    @staticmethod
    def _serialize_payload(payload: dict[str, Any] | None) -> str:
        return json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _normalize_schedule_time(when: datetime) -> datetime:
        if when.tzinfo is None:
            return when
        return when.astimezone(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _current_time() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
