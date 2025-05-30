from fastapi import Depends
from fastapi import APIRouter, Request, HTTPException
from app.factories.top_up_factory import TopUpStrategyFactory
from app.orchestrators.webhook_orchestrator import WebhookOrchestrator
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_async_session
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
        payload = await request.json()
        logger.info(f"[WEBHOOK] CryptoCloud payload: {payload}")

        # Проверка, что необходимое поле есть
        if "status" not in payload or "order_id" not in payload:
            logger.warning("[WEBHOOK] Invalid payload from CryptoCloud")
            raise HTTPException(status_code=400, detail="Invalid payload")

        # Получаем стратегию
        strategy = TopUpStrategyFactory.get_strategy("cryptocloud")

        # Обрабатываем callback
        callback_result = await strategy.process_callback(payload)

        if not callback_result.get("success"):
            logger.warning(f"[WEBHOOK] Callback handling failed: {callback_result.get('error')}")
            return {"status": "error"}

        # Обработка бизнес-логики
        orchestrator = WebhookOrchestrator(session)
        logger.warning(f"[WEBHOOK] Callback handling - orchestrator")
        await orchestrator.execute(callback_result)

        return {"status": "ok"}

    except Exception as e:
        logger.exception(f"[WEBHOOK ERROR] {e}")
        return {"status": "internal error"}