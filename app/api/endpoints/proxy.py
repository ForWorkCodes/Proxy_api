from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_async_session
from app.orchestrators.proxy import BuyProxyOrchestrator
from app.services import ProxyApiService
from app.models.proxy import Proxy
from app.models.transaction import Transaction
from app.schemas.proxy import ProxyBuyRequest, ProxyBuyResponse
import httpx
import logging
from datetime import datetime
from fastapi import Query

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/get_price")
async def get_proxy_price(
    telegram_id: str = Query(...),
    version: str = Query(...),
    quantity: int = Query(...),
    days: int = Query(...),
    session: AsyncSession = Depends(get_async_session)
):
    logger.info(
        f"Received /proxy/quote request from telegram_id={telegram_id}, "
        f"version={version}, quantity={quantity}, days={days}"
    )
    try:
        service = ProxyApiService(session)
        data = await service.get_proxy_price(version, quantity, days, telegram_id)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Price check failed")


@router.post("/buy_proxy")#response_model=ProxyBuyResponse
async def buy_proxy(
    request: ProxyBuyRequest,
    session: AsyncSession = Depends(get_async_session)
):
    orchestrator = BuyProxyOrchestrator(session)
    result = await orchestrator.execute(request)
    return result

    return ProxyBuyResponse(
        status="success",
        proxies=[{
            "ip": p.ip,
            "port": p.port,
            "type": p.type,
            "country": p.country,
            "date_end": p.date_end
        } for p in proxies]
    )
