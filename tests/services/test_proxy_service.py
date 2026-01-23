from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.sync_db import Base
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.models.proxy import Proxy
from app.schemas.proxy import ProxyItemDB
from app.services.proxy_service import ProxyService


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


async def _create_user(session: AsyncSession, telegram_id: str = "12345") -> User:
    user = User(
        telegram_id=telegram_id,
        chat_id="chat",
        username="username",
        firstname="First",
        language="en",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _create_proxy(
    session: AsyncSession,
    user_id: int,
    ip: str,
    port: int,
    auto_prolong: bool,
) -> Proxy:
    proxy = Proxy(
        user_id=user_id,
        proxy_id=f"proxy-{ip}-{port}",
        ip=ip,
        host=ip,
        port=port,
        type="http",
        transaction_id=1,
        active=True,
        auto_prolong=auto_prolong,
    )
    session.add(proxy)
    await session.commit()
    await session.refresh(proxy)
    return proxy


def _build_proxy_item(user_id: int, *, auto_prolong: bool) -> ProxyItemDB:
    now = datetime.now(timezone.utc)
    return ProxyItemDB(
        user_id=user_id,
        proxy_id="proxy-1",
        ip="10.0.0.10",
        transaction_id=123,
        host="10.0.0.10",
        port=3128,
        version=4,
        type="http",
        country="US",
        date=now,
        date_end=now + timedelta(days=1),
        unixtime=int(now.timestamp()),
        unixtime_end=int((now + timedelta(days=1)).timestamp()),
        descr="test proxy",
        active=True,
        provider="provider",
        auto_prolong=auto_prolong,
        days=1,
        login_proxy="user",
        pass_proxy="pass",
    )


@pytest.mark.asyncio
async def test_activate_proxy_prlong_enables_auto_prolong(async_session: AsyncSession):
    user = await _create_user(async_session)
    proxy = await _create_proxy(async_session, user.id, "10.0.0.1", 3128, auto_prolong=False)

    service = ProxyService(async_session)
    result = await service.activate_proxy_prlong(user, "10.0.0.1:3128")

    await async_session.refresh(proxy)

    assert result.success is True
    assert result.status_code == 200
    assert proxy.auto_prolong is True


@pytest.mark.asyncio
async def test_activate_proxy_prlong_returns_not_found(async_session: AsyncSession):
    user = await _create_user(async_session)
    service = ProxyService(async_session)

    result = await service.activate_proxy_prlong(user, "10.0.0.2:8080")

    assert result.success is False
    assert result.status_code == 404
    assert "not found" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_cancel_proxy_prlong_disables_auto_prolong(async_session: AsyncSession):
    user = await _create_user(async_session, telegram_id="67890")
    proxy = await _create_proxy(async_session, user.id, "10.0.0.3", 1080, auto_prolong=True)

    service = ProxyService(async_session)
    result = await service.cancel_proxy_prlong(user, "10.0.0.3:1080")

    assert result.success is True
    assert result.status_code == 200

    await async_session.refresh(proxy)
    assert proxy.auto_prolong is False


@pytest.mark.asyncio
async def test_create_proxy_schedules_notification_when_no_auto_prolong(
    async_session: AsyncSession,
):
    user = await _create_user(async_session)
    service = ProxyService(async_session)
    
    data = _build_proxy_item(user.id, auto_prolong=False)
    print("PROXY ITEM BUILD:")
    print("  proxy_id =", data.proxy_id)
    print("  date_end =", data.date_end)

    await service.create_proxy(data, notification=True)
    
    result = await async_session.execute(
        Notification.__table__.select().where(
            Notification.type == NotificationType.proxy_expiring
        )
    )
    rows = result.fetchall()

    print("NOTIFICATIONS FOUND:", len(rows))
    for i, row in enumerate(rows, start=1):
        print(f"  #{i}")
        print("    user_id =", row.user_id)
        print("    type =", row.type)
        print("    scheduled_at =", getattr(row, "scheduled_at", None))

    assert len(rows) == 1
    assert rows[0].user_id == user.id


@pytest.mark.asyncio
async def test_notification_time_in_multiple_timezones(async_session: AsyncSession):
    print(":")
    user = await _create_user(async_session)
    service = ProxyService(async_session)
    # Берём фиксированный unixtime_end (UTC)
    expires_at_utc = datetime(2026, 1, 26, 12, 0, 0, tzinfo=timezone.utc)
    unixtime_end = int(expires_at_utc.timestamp())

    data = _build_proxy_item(user.id, auto_prolong=False)
    data.unixtime_end = unixtime_end  # важно: int, не строка
    # date_end можно не трогать, если логика уже на unixtime_end

    await service.create_proxy(data, notification=True)

    result = await async_session.execute(
        Notification.__table__.select().where(
            Notification.type == NotificationType.proxy_expiring
        )
    )
    row = result.first()
    assert row is not None

    scheduled_at_db = row.scheduled_at  # скорее всего naive из sqlite

    scheduled_at_utc = scheduled_at_db.replace(tzinfo=timezone.utc)
    expected_notify_at_utc = expires_at_utc - timedelta(hours=24)
    print("scheduled_at_utc =", repr(scheduled_at_utc))
    print("expected_notify_at_utc =", repr(expected_notify_at_utc))
    assert scheduled_at_utc == expected_notify_at_utc


    # Проверяем “как это выглядит” в других TZ
    dublin = ZoneInfo("Europe/Dublin")
    ny = ZoneInfo("America/New_York")
    tokyo = ZoneInfo("Asia/Tokyo")

    assert scheduled_at_utc.astimezone(dublin).isoformat() == expected_notify_at_utc.astimezone(dublin).isoformat()
    assert scheduled_at_utc.astimezone(ny).isoformat() == expected_notify_at_utc.astimezone(ny).isoformat()
    assert scheduled_at_utc.astimezone(tokyo).isoformat() == expected_notify_at_utc.astimezone(tokyo).isoformat()

@pytest.mark.asyncio
async def test_create_proxy_skips_notification_when_auto_prolong_enabled(
    async_session: AsyncSession,
):
    user = await _create_user(async_session)
    service = ProxyService(async_session)
    data = _build_proxy_item(user.id, auto_prolong=True)

    await service.create_proxy(data, notification=True)

    result = await async_session.execute(Notification.__table__.select())
    rows = result.fetchall()
    assert rows == []
