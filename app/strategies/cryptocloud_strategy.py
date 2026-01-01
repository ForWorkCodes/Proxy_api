import httpx
import logging
import jwt
from app.interfaces.top_up_strategy import TopUpStrategy
from app.models.user import User
from app.core.config import settings
from fastapi import Request
from jwt import InvalidTokenError

logger = logging.getLogger(__name__)


class CryptoCloudStrategy(TopUpStrategy):
    def __init__(self):
        self.api_key = settings.CRYPTOCLOUD_API_KEY
        self.shop_id = settings.CRYPTOCLOUD_SHOP_ID
        self.shop_secret = settings.CRYPTOCLOUD_SECRET
        self.api_url = "https://api.cryptocloud.plus/v2/invoice/create"

    async def generate_link(self, user: User, amount: float, transaction_id: int) -> dict:
        payload = {
            "shop_id": self.shop_id,
            "amount": float(amount),
            "currency": "USD",
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

    async def process_callback(self, request: Request) -> dict:
        form = await request.form()
        payload = dict(form)
        logger.info(f"[WEBHOOK] CryptoCloud payload: {payload}")

        token = payload.get("token")
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        if not token:
            return {"status": "error", "error": "Missing token"}

        try:
            decoded = jwt.decode(
                token,
                self.shop_secret,
                algorithms=["HS256"],
                options={"require": ["exp", "id"]},
            )
        except InvalidTokenError as e:
            return {"status": "error", "error": f"Invalid token: {e}"}

        status = payload.get("status")
        invoice_id = payload.get("invoice_id")

        if decoded.get("id") != invoice_id:
            return {"status": "error", "error": "Token id mismatch"}

        return {
            "status": status,
            "invoice_id": "INV-" + invoice_id,
        }

    def get_name(self) -> str:
        return "cryptocloud"
