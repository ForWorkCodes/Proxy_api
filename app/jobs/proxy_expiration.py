import typer
import asyncio
from app.services.proxy_service import ProxyService
from app.core.db import get_async_session
from datetime import datetime, timezone
from app.core.logging_config import setup_logging
import logging

app = typer.Typer()

LOG_DIR = "/app/logs"
setup_logging()

logger = logging.getLogger(__name__)
logger.propagate = True


@app.command()
def deactivate():
    """Deactivate expired proxies"""
    print("=== LOGGING DEBUG ===")
    print(logging.getLogger().handlers)
    logger.info("TEST LOG: CLI start")

    async def run():
        session_gen = get_async_session()
        session = await session_gen.__anext__()

        try:
            proxy_service = ProxyService(session)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            logger.info(f"[CRON] Start check at {now.isoformat()}")
            print(f"[CRON] Start check at {now.isoformat()}")

            expiring = await proxy_service.get_active_proxy_by_date(now)
            if not expiring:
                print("[CRON] No proxies found")
                return

            for p in expiring:
                logger.info(f"[EXPIRED] {p.ip}:{p.port} ends at {p.date_end}")
                print(f"[EXPIRED] {p.ip}:{p.port} ends at {p.date_end}")
            await proxy_service.deactivate_proxy_list(expiring)
        finally:
            await session_gen.aclose()
    asyncio.run(run())
