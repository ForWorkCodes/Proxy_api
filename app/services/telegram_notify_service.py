import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


class TelegramNotifyService:
    def __init__(self):
        self.endpoint = settings.TELEGRAM_NOTIFY_URL.rstrip("/") + "/notify"
        self.api_key = settings.INTERNAL_API_TOKEN

    async def send_message(self, user_id: int, message: str) -> bool:
        payload = {
            "telegram_id": user_id,
            "text": message
        }
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.endpoint, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                if not data.get("success"):
                    logger.warning(f"Telegram notify failed: {data}")
                    return False
                return True
        except Exception as e:
            logger.exception(f"Failed to send telegram message: {e}")
            return False
