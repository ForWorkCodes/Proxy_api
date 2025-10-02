import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.sync_db import Base
from app.models.currency_rate import CurrencyRate
from app.services.currency_service import CurrencyService, CurrencyProviderError


@pytest_asyncio.fixture
async def async_session():
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


@pytest.mark.asyncio
async def test_convert_price_uses_latest_snapshot(async_session: AsyncSession):
    service = CurrencyService(async_session)
    now = datetime.now(timezone.utc)
    async_session.add_all([
        CurrencyRate(
            provider="moex",
            base_currency="USD",
            quote_currency="RUB",
            rate=95.0,
            created_at=now - timedelta(minutes=5),
        ),
        CurrencyRate(
            provider="moex",
            base_currency="USD",
            quote_currency="RUB",
            rate=81.5,
            created_at=now,
        ),
    ])
    await async_session.commit()

    usd_amount = await service.convert_price(400.0, provider="moex")
    assert usd_amount == pytest.approx(4.9079754601226995)


@pytest.mark.asyncio
async def test_convert_price_falls_back_to_cbr(async_session: AsyncSession):
    service = CurrencyService(async_session)
    async_session.add(
        CurrencyRate(
            provider="cbr",
            base_currency="USD",
            quote_currency="RUB",
            rate=90.0,
        )
    )
    await async_session.commit()

    usd_amount = await service.convert_price(9000.0, provider="moex")
    assert usd_amount == pytest.approx(100.0)


@pytest.mark.asyncio
async def test_convert_price_raises_when_no_rates(async_session: AsyncSession):
    service = CurrencyService(async_session)
    with pytest.raises(CurrencyProviderError):
        await service.convert_price(1000.0, provider="moex")
