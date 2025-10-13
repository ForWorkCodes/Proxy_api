from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from app.core.db import get_async_session
from app.orchestrators.proxy import BuyProxyOrchestrator
from app.services import ProxyApiService, ProxyService, UserService
from app.schemas.proxy import ProxyBuyRequest, ProxyItem, ProxyGetRequest, ProxyCheckRequest, ProxyLinkRequest
from app.core.constants import REVERSE_PROXY_TYPE_MAPPING
import httpx
import logging
from fastapi import Query
import ipaddress
import re

router = APIRouter()
logger = logging.getLogger(__name__)


class ProxyCancellationRequestError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _build_error_response(status_code: int, message: str) -> dict:
    return {
        "success": False,
        "status_code": status_code,
        "error": message,
    }


def _sanitize_proxy_address(address: str) -> str:
    if not address:
        raise ProxyCancellationRequestError(400, "Proxy address is required")

    sanitized = address.strip().lower()
    if len(sanitized) > 300:
        raise ProxyCancellationRequestError(400, "Proxy address is too long")

    if not re.fullmatch(r"[a-z0-9.-]+:\d{1,5}", sanitized):
        raise ProxyCancellationRequestError(400, "Invalid proxy address format")

    host, port_raw = sanitized.rsplit(":", 1)

    try:
        port = int(port_raw)
    except ValueError as exc:
        raise ProxyCancellationRequestError(400, "Proxy port must be numeric") from exc

    if not (1 <= port <= 65535):
        raise ProxyCancellationRequestError(400, "Proxy port is out of range")

    if _is_ipv4(host):
        return sanitized

    if not _is_allowed_domain(host):
        raise ProxyCancellationRequestError(400, "Proxy host contains invalid characters")

    return sanitized


def _is_ipv4(host: str) -> bool:
    try:
        ipaddress.IPv4Address(host)
        return True
    except ipaddress.AddressValueError:
        return False


def _is_allowed_domain(host: str) -> bool:
    if host.startswith("-") or host.endswith("-"):
        return False
    if ".." in host:
        return False

    labels = host.split(".")
    if any(len(label) == 0 or len(label) > 63 for label in labels):
        return False

    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    return all(all(ch in allowed for ch in label) for label in labels)


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
        data = await service.get_proxy_price(version, quantity, days, telegram_id+"-telegram")
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


@router.post("/cancel-proxy")
async def cancel_proxy(
    request: ProxyCheckRequest,
    session: AsyncSession = Depends(get_async_session)
):
    logger.info(
        f"Received /cancel_proxy request from telegram_id={request.telegram_id}, "
        f"address={request.address}"
    )
    try:
        telegram_id = request.telegram_id
        try:
            address = _sanitize_proxy_address(request.address)
        except ProxyCancellationRequestError as exc:
            logger.warning(
                "[CANCEL AUTO PROLONG] Invalid address from telegram_id=%s: %s",
                telegram_id,
                exc.message,
            )
            return _build_error_response(exc.status_code, exc.message)

        user_service = UserService(session)
        user = await user_service.get_user_by_telegram_id(telegram_id)

        if not user or not user:
            logger.warning(f"[USER FAILED] User or balance not found for telegram_id={telegram_id}")
            return _build_error_response(404, "User or balance not found")

        service = ProxyService(session)
        data = await service.cancel_proxy_prlong(user, address)

        if data.success:
            return {
                "success": True,
                "status_code": 200
            }
        else:
            return _build_error_response(404, data.message or "Updating failed")
    except ValueError as exc:
        logger.warning(
            "[CANCEL AUTO PROLONG] Validation failed for telegram_id=%s: %s",
            request.telegram_id,
            exc,
        )
        return _build_error_response(400, str(exc))
    except SQLAlchemyError:
        logger.exception(
            "[CANCEL AUTO PROLONG] Database error for telegram_id=%s, address=%s",
            request.telegram_id,
            request.address,
        )
        return _build_error_response(500, "Database error occurred")
    except httpx.HTTPError:
        logger.exception(
            "[CANCEL AUTO PROLONG] Upstream HTTP error for telegram_id=%s",
            request.telegram_id,
        )
        return _build_error_response(502, "Price check failed")
    except Exception:
        logger.exception(
            "[CANCEL AUTO PROLONG] Unexpected error for telegram_id=%s",
            request.telegram_id,
        )
        return _build_error_response(500, "Internal server error")


@router.post("/get-link-proxy")
async def checker_proxy(
    request: ProxyLinkRequest,
    session: AsyncSession = Depends(get_async_session)
):
    logger.info(
        f"Received /get-link-proxy request from telegram_id={request.telegram_id}, "
        f"file_type={request.file_type}"
    )
    try:
        if request.file_type == "csv":
            file = request.file_type
        else:
            file = "xls"

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
        data = await proxy_service.make_link_proxy_list(user, file)
        return data
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail="Price check failed")
