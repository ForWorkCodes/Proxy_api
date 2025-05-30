from fastapi import APIRouter, Request, Depends
from app.orchestrators.webhook_orchestrator import WebhookOrchestrator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_async_session
from app.factories.top_up_factory import TopUpStrategyFactory
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/webhook/nowpayments/")
async def nowpayments_webhook(request: Request, session: AsyncSession = Depends(get_async_session)):
    payload = await request.json()
    logger.info(f"[WEBHOOK] NowPayments payload: {payload}")

    try:
        orchestrator = WebhookOrchestrator(session)
        await orchestrator.execute(payload)

        strategy = TopUpStrategyFactory.get_strategy("nowpayments")
        data = await strategy.process_callback(payload)

        if not data["success"]:
            logger.warning(f"[WEBHOOK] Processing failed: {data['error']}")
            return {"status": "error"}

        return {"status": "ok"}

    except Exception as e:
        logger.exception(f"[WEBHOOK ERROR] {e}")
        return {"status": "internal error"}


@router.post("/webhook/cryptocloud/")
async def cryptocloud_webhook(request: Request, session: AsyncSession = Depends(get_async_session)):
    try:
        strategy = TopUpStrategyFactory.get_strategy("cryptocloud")
        data = await strategy.process_callback(request)

        orchestrator = WebhookOrchestrator(session)
        result = await orchestrator.execute(data)
        return result
    except Exception as e:
        logger.exception(f"[WEBHOOK ERROR] {e}")
        return {"status": "internal error"}