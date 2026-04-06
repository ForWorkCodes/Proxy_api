from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.sync_db import Base
from app.models.balance import Balance
from app.models.currency_rate import CurrencyRate
from app.models.notification import Notification, NotificationType
from app.models.proxy import Proxy
from app.models.transaction import Transaction
from app.models.user import User
from app.orchestrators.proxy import BuyProxyOrchestrator
from app.schemas.proxy import ProxyBuyRequest


@pytest_asyncio.fixture
async def async_session() -> AsyncSession:
    pytest.importorskip("aiosqlite")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_maker = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    try:
        async with async_session_maker() as session:
            yield session
    finally:
        await engine.dispose()


async def _create_user_with_balance(
    session: AsyncSession,
    *,
    telegram_id: str = "123",
    amount: float = 100.0,
    notifications_enabled: bool = True,
) -> User:
    user = User(
        telegram_id=telegram_id,
        chat_id="chat",
        username="username",
        firstname="First",
        language="en",
        notification=notifications_enabled,
    )
    session.add(user)
    await session.flush()

    session.add(
        Balance(
            user_id=user.id,
            amount=amount,
        )
    )
    await session.commit()
    await session.refresh(user, attribute_names=["balance"])
    return user


async def _seed_currency_rate(session: AsyncSession, *, rate: float = 100.0) -> None:
    session.add(
        CurrencyRate(
            provider="moex",
            base_currency="USD",
            quote_currency="RUB",
            rate=rate,
            created_at=datetime.now(timezone.utc),
        )
    )
    await session.commit()


def _build_request() -> ProxyBuyRequest:
    return ProxyBuyRequest(
        telegram_id="123",
        version="ipv4",
        type="https",
        country="us",
        days=30,
        quantity=1,
        auto_prolong=False,
    )


def _httpx_response(url: str, payload: dict, status_code: int = 200) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(status_code, json=payload, request=request)


@pytest.mark.asyncio
async def test_buy_proxy_persists_purchase_and_updates_balance(async_session: AsyncSession) -> None:
    user = await _create_user_with_balance(async_session, amount=100.0)
    await _seed_currency_rate(async_session, rate=100.0)

    getprice_response = _httpx_response(
        "https://proxy.site/proxy/getprice",
        {
            "status": "yes",
            "price_single": "1000",
            "price": "1000",
            "period": 30,
            "count": 1,
        },
    )
    buy_response = _httpx_response(
        "https://proxy.site/proxy/buy",
        {
            "status": "yes",
            "country": "us",
            "period": 30,
            "list": {
                "proxy1": {
                    "ip": "1.2.3.4",
                    "host": "1.2.3.4",
                    "port": 8080,
                    "version": 4,
                    "type": "https",
                    "user": "login123",
                    "pass": "pass123",
                    "date": "2026-01-01 00:00:00",
                    "date_end": "2026-01-31 00:00:00",
                    "unixtime": 1767225600,
                    "unixtime_end": 1769817600,
                    "descr": "test proxy",
                    "active": True,
                }
            },
        },
    )

    with patch("app.services.proxy_api_service.httpx.AsyncClient.get", new=AsyncMock(side_effect=[getprice_response, buy_response])):
        result = await BuyProxyOrchestrator(async_session).execute(_build_request())

    await async_session.refresh(user, attribute_names=["balance"])

    assert result.success is True
    assert result.status_code == 200
    assert result.price == 13.0
    assert result.quantity == 1
    assert result.country == "us"
    assert result.proxies[0].host == "1.2.3.4"
    assert result.proxies[0].version == "ipv4"

    assert user.balance.amount == 87.0

    proxies = (await async_session.execute(select(Proxy))).scalars().all()
    assert len(proxies) == 1
    assert proxies[0].user_id == user.id
    assert proxies[0].transaction_id is not None
    assert proxies[0].auto_prolong is False

    transactions = (
        await async_session.execute(select(Transaction).order_by(Transaction.id))
    ).scalars().all()
    assert len(transactions) == 1
    assert transactions[0].type == "proxy"
    assert transactions[0].status == "completed"
    assert "Purchase complete" in (transactions[0].comment or "")

    notifications = (await async_session.execute(select(Notification))).scalars().all()
    assert len(notifications) == 1
    assert notifications[0].user_id == user.id
    assert notifications[0].type == NotificationType.proxy_expiring
    assert notifications[0].sent is False


@pytest.mark.asyncio
async def test_buy_proxy_refunds_balance_when_provider_request_fails(async_session: AsyncSession) -> None:
    user = await _create_user_with_balance(async_session, amount=100.0)
    await _seed_currency_rate(async_session, rate=100.0)

    getprice_response = _httpx_response(
        "https://proxy.site/proxy/getprice",
        {
            "status": "yes",
            "price_single": "1000",
            "price": "1000",
            "period": 30,
            "count": 1,
        },
    )
    request_error = httpx.RequestError(
        "provider unavailable",
        request=httpx.Request("GET", "https://proxy.site/proxy/buy"),
    )

    with patch(
        "app.services.proxy_api_service.httpx.AsyncClient.get",
        new=AsyncMock(side_effect=[getprice_response, request_error]),
    ):
        result = await BuyProxyOrchestrator(async_session).execute(_build_request())

    await async_session.refresh(user, attribute_names=["balance"])

    assert result["success"] is False
    assert result["status_code"] == 502
    assert "Proxy API error" in result["error"]
    assert user.balance.amount == 100.0

    proxies = (await async_session.execute(select(Proxy))).scalars().all()
    assert proxies == []

    transactions = (
        await async_session.execute(select(Transaction).order_by(Transaction.id))
    ).scalars().all()
    assert len(transactions) == 2

    purchase_tx, refund_tx = transactions
    assert purchase_tx.type == "proxy"
    assert purchase_tx.status == "failed"
    assert "Purchase failed" in (purchase_tx.comment or "")

    assert refund_tx.type == "refund"
    assert refund_tx.status == "paid"
    assert refund_tx.balance_after == 100.0

    notifications = (await async_session.execute(select(Notification))).scalars().all()
    assert notifications == []
