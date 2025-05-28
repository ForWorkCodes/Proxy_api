from sqlalchemy.ext.asyncio import AsyncSession
from app.core.constants import PROXY_TYPE_MAPPING
from app.core.config import settings
from app.services.proxy_service import ProxyService
import httpx
import logging

logger = logging.getLogger(__name__)


class ProxyApiService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.proxy_service = ProxyService(session)
        self.headers = {
            "X-Internal-Token": settings.INTERNAL_API_TOKEN
        }

    async def get_proxy_price(self, version: str, quantity: int, days: int, telegram_id: str) -> dict:
        if version not in PROXY_TYPE_MAPPING:
            logger.warning(f"Invalid proxy version received: {version}")
            return {
                "success": False,
                "status_code": 400,
                "error": "Invalid proxy version"
            }

        api_version = PROXY_TYPE_MAPPING[version]
        api_url = f"{settings.PROXY_API_URL}/{settings.PROXY_API_KEY}/getprice"
        params = {
            "version": api_version,
            "count": quantity,
            "period": days
        }

        logger.info(f"Requesting price from external API: {api_url} with params {params}")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, params=params)
                response.raise_for_status()
                price_data = response.json()
                logger.info(f"Received price data: {price_data}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP status error from proxy API: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "status_code": e.response.status_code,
                "error": e.response.text
            }
        except httpx.RequestError as e:
            logger.error(f"Request error when connecting to proxy API: {e}")
            return {
                "success": False,
                "status_code": 502,
                "error": "Failed to connect to proxy API"
            }
        except Exception as e:
            logger.exception(f"Unexpected error during price request: {e}")
            return {
                "success": False,
                "status_code": 500,
                "error": "Internal server error"
            }

        if price_data.get("status") != "yes":
            logger.warning(f"Proxy API returned error: {price_data.get('error')}")
            return {
                "success": False,
                "status_code": 400,
                "error": price_data.get("error", "Unknown error")
            }

        logger.info(
            f"Returning quote: price={price_data['price']}, price_single={price_data['price_single']} "
            f"for telegram_id={telegram_id}"
        )

        total_price = round(float(price_data["price"]) * (1 + 30 / 100))

        return {
            "success": True,
            "status_code": 200,
            "total_price": total_price,
            "price_single": price_data["price_single"],
            "days": price_data["period"],
            "currency": "USD",
            "version": version,
            "quantity": price_data["count"]
        }

    async def buy_proxy(self, version: str, quantity: int, days: int, country: str, type_proxy: str, telegram_id: str) -> dict:
        if version not in PROXY_TYPE_MAPPING:
            logger.warning(f"Invalid proxy version received: {version}")
            return {
                "success": False,
                "status_code": 400,
                "error": "Invalid proxy version"
            }

        api_version = PROXY_TYPE_MAPPING[version]
        api_url = f"{settings.PROXY_API_URL}/{settings.PROXY_API_KEY}/buy"
        params = {
            "count": quantity,
            "period": days,
            "country": country,
            "version": api_version,
            "type": type_proxy,
            "auto_renew": 0
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(api_url, params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as e:
                logger.error(f"Proxy API error: {e}")
                return {
                    "success": False,
                    "status_code": 502,
                    "error": f"Proxy API error: {e}"
                }

        if data.get("status") != "yes":
            if data.get("error_id") == 400:
                print("Нет денег")
                #TODO: сделать экстренное оповещение о недостаточном количестве денег

            return {
                "success": False,
                "status_code": data.get("error_id"),
                "error": data.get("error", "Unknown error")
            }

        return {
            "success": True,
            "status_code": 200,
            "data": data
        }

    async def check_proxy(self, telegram_id: str, address: str) -> dict:
        try:
            host, port_str = address.split(":")
            port = int(port_str)
        except ValueError:
            return {
                "success": False,
                "status_code": 400,
                "error": "Invalid address format. Use 'IP:PORT'"
            }

        proxy = await self.proxy_service.get_proxy_by_telegram_ip_port(telegram_id, host, port)

        if proxy and proxy.proxy_id:
            print("Найден прокси:", proxy.host, proxy.port)
        else:
            print(proxy)
            return {
                "success": False,
                "status_code": 404,
                "error": "Proxy not found"
            }

        api_url = f"{settings.PROXY_API_URL}/{settings.PROXY_API_KEY}/check"
        params = {
            "ids": proxy.proxy_id
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(api_url, params=params)
                response.raise_for_status()
                check_data = response.json()
                logger.info(f"Received check proxy: {check_data}")
        except httpx.RequestError as e:
            logger.error(f"Request error when connecting to proxy API: {e}")
            return {
                "success": False,
                "status_code": 502,
                "error": "Failed to connect to proxy API"
            }
        except Exception as e:
            logger.exception(f"Unexpected error during check request: {e}")
            return {
                "success": False,
                "status_code": 500,
                "error": "Internal server error"
            }

        if check_data.get("status") != "yes":
            logger.warning(f"Proxy API returned error: {check_data.get('error')}")
            return {
                "success": True,
                "status_code": 200,
                "proxy_status": False,
                "error": check_data.get("error", "Unknown error")
            }

        return {
            "success": True,
            "status_code": 200,
            "proxy_status": check_data.get("proxy_status")
        }
