import asyncio
import logging
from datetime import datetime, timezone

import typer

from app.core.db import get_async_session
from app.core.logging_config import setup_logging
from app.services.currency_service import CurrencyService

app = typer.Typer()

LOG_DIR = "/app/logs"
setup_logging()

logger = logging.getLogger(__name__)
logger.propagate = True


@app.command()
def collect(
    provider: str = typer.Option("moex", "--provider", "-p", help="Which provider to call (moex or cbr)."),
    interval: int = typer.Option(3600, "--interval", "-i", help="Seconds between successive pulls."),
    run_once: bool = typer.Option(False, "--run-once", help="Fetch a single snapshot and exit."),
):
    """Fetches RUB/USD rate and stores it in the database on a schedule."""

    if not run_once and interval <= 0:
        raise typer.BadParameter("Interval must be positive when running continuously.")

    async def _runner() -> None:
        session_gen = get_async_session()
        session = await session_gen.__anext__()
        service = CurrencyService(session)

        try:
            while True:
                started_at = datetime.now(timezone.utc)
                logger.info("Starting currency rate collection at %s", started_at.isoformat())
                try:
                    snapshot = await service.fetch_and_record_rate(provider=provider)
                except Exception:
                    logger.exception("Failed to persist currency rate snapshot")
                else:
                    logger.info(
                        "Stored %s/%s rate %.6f from %s",
                        snapshot.base_currency,
                        snapshot.quote_currency,
                        snapshot.rate,
                        snapshot.provider,
                    )

                if run_once:
                    break

                await asyncio.sleep(interval)
        finally:
            await session_gen.aclose()

    asyncio.run(_runner())
