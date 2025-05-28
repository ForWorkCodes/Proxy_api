from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_async_session
from app.orchestrators.proxy import BuyProxyOrchestrator
from app.services import ProxyApiService, ProxyService, UserService
from app.schemas.proxy import ProxyBuyRequest, ProxyItem, ProxyGetRequest, ProxyCheckRequest
from app.core.constants import REVERSE_PROXY_TYPE_MAPPING
import httpx
import logging
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


@router.post("/get-proxy-telegram-id")
async def get_proxy(
    request: ProxyGetRequest,
    session: AsyncSession = Depends(get_async_session)
):
    logger.info(
        f"Received /get-proxy-telegram-id request from telegram_id={request.telegram_id}"
    )

    telegram_id = request.telegram_id
    user_service = UserService(session)
    user = await user_service.get_user_by_telegram_id(telegram_id)
    if not user or not user:
        logger.warning(f"[USER FAILED] User or balance not found for telegram_id={telegram_id}")
        return {
            "success": False,
            "status_code": 404,
            "error": "User or balance not found"
        }

    proxy_service = ProxyService(session)
    proxies = await proxy_service.get_list_proxy_by_user(user)

    proxy_dicts = []
    for p in proxies:
        item = ProxyItem.from_orm(p).dict()
        item["version"] = REVERSE_PROXY_TYPE_MAPPING.get(str(p.version), "unknown")
        proxy_dicts.append(item)

    if not proxies:
        return {
            "success": False,
            "status_code": 2001,
            "error": "No proxies found"
        }
    else:
        return {
            "success": True,
            "status_code": 200,
            "error": "",
            "proxies": proxy_dicts
        }


@router.post("/checker-proxy")
async def checker_proxy(
    request: ProxyCheckRequest,
    session: AsyncSession = Depends(get_async_session)
):
    logger.info(
        f"Received /checker_proxy request from telegram_id={request.telegram_id}, "
        f"address={request.address}"
    )
    try:
        service = ProxyApiService(session)
        data = await service.check_proxy(request.telegram_id, request.address)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Price check failed")
