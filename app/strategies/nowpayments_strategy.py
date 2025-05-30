import httpx
from app.interfaces.top_up_strategy import TopUpStrategy
from app.models.user import User
from app.core.config import settings
from fastapi import Request
import logging

logger = logging.getLogger(__name__)


class NowPaymentsStrategy(TopUpStrategy):
    def __init__(self):
        self.api_key = settings.CRYPTO_API_KEY_NOW_PAY
        self.api_url = "https://api.nowpayments.io/v1/invoice"

    async def generate_link(self, user: User, amount: float, transaction_id: int) -> dict:
        payload = {
            "price_amount": float(amount),
            "price_currency": "usd",
            #"pay_currency": "usdt",
            "order_id": f"user_{user.id}_tid_{transaction_id}",
            "order_description": f"Top-up for user {user.telegram_id}",
            "ipn_callback_url": "http://88.210.3.44/api/v1/webhook/nowpayments",
            "success_url": "https://nowpayments.io",
            "cancel_url": "https://nowpayments.io"
        }

        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.api_url, json=payload, headers=headers)
                print('------------------------------------------------------')
                print(await response.aread())
                print('------------------------------------------------------')

                if response.status_code != 200:
                    error = f"[NowPayments] Bad status {response.status_code}: {response.text}"
                    error_res = f"Bad status {response.status_code}"
                    logger.error(error)
                    return {
                        "success": False,
                        "link": "",
                        "error": error_res
                    }

                data = response.json()

                if "invoice_url" not in data:
                    error = f"[NowPayments] No invoice_url in response: {data}"
                    error_res = f"No invoice_url in response: {data}"
                    logger.error(error)
                    return {
                        "success": False,
                        "link": "",
                        "error": error_res
                    }

                return {
                    "success": True,
                    "link": data["invoice_url"],
                    "error": ""
                }

        except httpx.HTTPError as e:
            error = f"[NowPayments] HTTP error: {e}"
            error_res = f"HTTP error: {e}"
            logger.exception(error)
            return {
                "success": False,
                "link": "",
                "error": error_res
            }
        except Exception as e:
            error = f"[NowPayments] Unexpected error: {e}"
            error_res = f"Unexpected error: {e}"
            logger.exception(error)
            return {
                "success": False,
                "link": "",
                "error": error_res
            }

    async def process_callback(self, request: Request) -> dict:
        payload = await request.json()
        status = payload.get("payment_status")
        order_id = payload.get("order_id")

        if status == "confirmed":
            return {
                "success": True,
                "telegram_id": payload.get("custom_telegram_id"),
                "amount": float(payload.get("pay_amount")),
                "txid": payload.get("payment_id"),
                "comment": "Crypto payment success"
            }

        return {
            "success": False,
            "error": f"Unhandled status: {status}"
        }

    def get_name(self) -> str:
        return "newpayment"
