import httpx
from app.interfaces.top_up_strategy import TopUpStrategy
from app.models.user import User
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class CryptoCloudStrategy(TopUpStrategy):
    def __init__(self):
        self.api_key = settings.CRYPTOCLOUD_API_KEY
        self.shop_id = settings.CRYPTOCLOUD_SHOP_ID
        self.api_url = "https://api.cryptocloud.plus/v2/invoice/create"

    async def generate_link(self, user: User, amount: float, transaction_id: int) -> dict:
        payload = {
            "shop_id": self.shop_id,
            "amount": float(amount),
            "currency": "RUB",
            "order_id": f"user_{user.id}_tid_{transaction_id}"
        }

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)

                if response.status_code != 200:
                    error = f"[CryptoCloud] Bad status {response.status_code}: {response.text}"
                    logger.error(error)
                    return {
                        "success": False,
                        "link": "",
                        "error": error
                    }

                data = response.json()

                if data.get("status") != "success" or "result" not in data or "link" not in data["result"]:
                    error = f"[CryptoCloud] Unexpected response: {data}"
                    logger.error(error)
                    return {
                        "success": False,
                        "link": "",
                        "error": error
                    }

                return {
                    "success": True,
                    "link": data["result"]["link"],
                    "invoice_id": data["result"]["uuid"],
                    "error": ""
                }

        except httpx.HTTPError as e:
            error = f"[CryptoCloud] HTTP error: {e}"
            logger.exception(error)
            return {
                "success": False,
                "link": "",
                "error": error
            }
        except Exception as e:
            error = f"[CryptoCloud] Unexpected error: {e}"
            logger.exception(error)
            return {
                "success": False,
                "link": "",
                "error": error
            }

    async def process_callback(self, payload: dict) -> dict:
        status = payload.get("status")
        order_id = payload.get("order_id")

        if status == "paid":
            # Извлекаем telegram_id из order_id, если он закодирован в формате "user_{telegram_id}_tid_{transaction_id}"
            try:
                telegram_id = int(order_id.split("_")[1])
            except (IndexError, ValueError):
                telegram_id = None

            return {
                "success": True,
                "telegram_id": telegram_id,
                "amount": float(payload.get("amount", 0)),
                "txid": payload.get("uuid"),
                "comment": "CryptoCloud payment success"
            }

        return {
            "success": False,
            "error": f"Unhandled status: {status}"
        }
