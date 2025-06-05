import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.notification import Notification, NotificationType
from app.services.user_service import UserService
from app.services.telegram_notify_service import TelegramNotifyService


class NotificationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.telegram = TelegramNotifyService()
        self.user_service = UserService(session)

    async def process_pending(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        stmt = select(Notification).where(
            Notification.scheduled_at <= now,
            Notification.sent == False
        )
        result = await self.session.execute(stmt)
        notifications = result.scalars().all()

        for notif in notifications:

            # User in for: Плохо! Переделать!
            user = await self.user_service.get_user_by_id(notif.user_id)

            if user:
                language = user.language
            else:
                language = "ru"

            payload = json.loads(notif.payload or '{}')
            payload["language"] = language

            await self.telegram.send_message(notif.owner.telegram_id, payload)

            notif.sent = True
            notif.sent_at = now
            self.session.add(notif)

        await self.session.commit()

    async def schedule_notification(self, user_id: int, note_type: NotificationType, when: datetime, payload: dict):
        notif = Notification(
            user_id=user_id,
            type=note_type,
            scheduled_at=when,
            payload=json.dumps(payload),
            sent=False
        )
        self.session.add(notif)
        await self.session.commit()
