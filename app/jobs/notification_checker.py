import typer
import asyncio
from app.services.proxy_service import NotificationService
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
def check_expired():
    """Check almost expired proxies"""
    print("=== LOGGING DEBUG ===")

    async def run():
        session_gen = get_async_session()
        session = await session_gen.__anext__()

        try:
            not_service = NotificationService(session)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            logger.info(f"[CRON] Start check at {now.isoformat()}")
            print(f"[CRON] Start check at {now.isoformat()}")

            await not_service.process_pending()

        finally:
            await session_gen.aclose()
    asyncio.run(run())
