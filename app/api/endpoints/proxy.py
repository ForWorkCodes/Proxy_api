from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.db import get_async_session
from app.models.user import User
from app.models.balance import Balance
from app.core.constants import PROXY_TYPE_MAPPING
from app.models.proxy import Proxy
from app.models.transaction import Transaction
from app.schemas.proxy import ProxyBuyRequest, ProxyBuyResponse
from app.core.config import settings
import httpx
import logging
from datetime import datetime, timezone
from fastapi import Query

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/get_price")
async def get_proxy_price(
    telegram_id: str = Query(...),
    version: str = Query(...),
    quantity: int = Query(...),
    days: int = Query(...)
):
    logger.info(
        f"Received /proxy/quote request from telegram_id={telegram_id}, "
        f"version={version}, quantity={quantity}, days={days}"
    )
    try:
        data = await get_proxy_price_logic(version, quantity, days, telegram_id)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Price check failed")


async def get_proxy_price_logic(version: str, quantity: int, days: int, telegram_id: str) -> dict:
    if version not in PROXY_TYPE_MAPPING:
        logger.warning(f"Invalid proxy version received: {version}")
        raise HTTPException(status_code=400, detail="Invalid proxy version")

    api_version = PROXY_TYPE_MAPPING[version]
    api_url_price = f"{settings.PROXY_API_URL}/{settings.PROXY_API_KEY}/getprice"
    params_price = {
        "version": api_version,
        "count": quantity,
        "period": days
    }

    logger.info(f"Requesting price from external API: {api_url_price} with params {params_price}")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(api_url_price, params=params_price)
            response.raise_for_status()
            price_data = response.json()
            logger.info(f"Received price data: {price_data}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error when requesting price from proxy API: {e}")
            raise HTTPException(status_code=502, detail="Price check failed")
        except Exception as e:
            logger.exception(f"Unexpected error during price request: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

    if price_data.get("status") != "yes":
        logger.warning(f"Proxy API returned error: {price_data.get('error')}")
        raise HTTPException(status_code=400, detail=price_data.get("error", "Unknown error"))

    logger.info(
        f"Returning quote: price={price_data['price']}, price_single={price_data['price_single']} "
        f"for telegram_id={telegram_id}"
    )

    return {
        "total_price": price_data["price"],
        "price_single": price_data["price_single"],
        "days": price_data["period"],
        "currency": "USD",
        "version": version,
        "quantity": price_data["count"]
    }

@router.post("/buy_proxy", response_model=ProxyBuyResponse)
async def buy_proxy(
    request: ProxyBuyRequest,
    session: AsyncSession = Depends(get_async_session)
):
    return
    try:
        data_price = await get_proxy_price_logic(request.version, request.quantity, request.days, request.telegram_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Price check failed")

    # Получить пользователя и баланс
    result = await session.execute(select(User).where(User.telegram_id == request.telegram_id))
    user = result.scalar_one_or_none()
    if not user or not user.balance:
        raise HTTPException(status_code=404, detail="User or balance not found")

    # Проверка баланса
    if user.balance.amount < data_price["total_price"]:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Запрос к proxy6.net
    api_url = f"{settings.PROXY_API_URL}/{settings.PROXY_API_KEY}/buy"
    params = {
        "count": request.quantity,
        "period": request.days,
        "country": request.country,
        "version": request.version,
        "type": request.type,
        "auto_renew": 0
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            logger.error(f"Proxy API error: {e}")
            raise HTTPException(status_code=502, detail="Proxy API error")

    if data.get("status") != "yes":
        raise HTTPException(status_code=400, detail=data.get("error", "Unknown error"))

    # Сохранение прокси, транзакции и обновление баланса
    proxies = []
    for p in data["list"]:
        proxy = Proxy(
            user_id=user.id,
            proxy_id=p["id"],
            ip=p["ip"],
            host=p["host"],
            port=p["port"],
            user=p["user"],
            password=p["pass"],
            type=p["type"],
            country=p["country"],
            date=datetime.utcfromtimestamp(p["date"]),
            date_end=datetime.utcfromtimestamp(p["date_end"]),
            unixtime=p["unixtime"],
            unixtime_end=p["unixtime_end"],
            descr=p["descr"],
            active=True
        )
        session.add(proxy)
        proxies.append(proxy)

    # Списание средств
    total_cost = float(data.get("price"))
    user.balance.amount -= total_cost

    # Лог транзакции
    transaction = Transaction(
        user_id=user.id,
        amount=-total_cost,
        balance_after=user.balance.amount,
        type="purchase",
        provider="proxy6.net",
        comment=f"Buy {request.quantity} proxies"
    )
    session.add(transaction)

    await session.commit()

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
