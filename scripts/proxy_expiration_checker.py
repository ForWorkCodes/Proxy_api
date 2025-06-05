from app.services.proxy_service import ProxyService
from datetime import datetime, timezone
from app.core.db import get_async_session
import logging

logger = logging.getLogger(__name__)


async def main():
    async with get_async_session() as session:
        proxy_service = ProxyService(session)
        now = datetime.now(timezone.utc)

        logger.info(f"[CRON] Started proxy expiration check at {now.isoformat()}")

        expiring_proxies = await proxy_service.get_active_proxy_by_date(now)
        if not expiring_proxies:
            logger.info("[CRON] No expired proxies found.")
            return

        for proxy in expiring_proxies:
            logger.info(
                f"[EXPIRED] Proxy id={proxy.id}, ip={proxy.ip}, port={proxy.port}, "
                f"host={proxy.host}, date_end={proxy.date_end.isoformat()}"
            )

        await proxy_service.deactivate_proxy_list(expiring_proxies)

        logger.info(f"[CRON] Deactivated {len(expiring_proxies)} expired proxies.")
        print(f"Deactivated {len(expiring_proxies)} proxies.")
