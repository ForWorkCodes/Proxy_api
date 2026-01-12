import json
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.sync_db import Base
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.schemas.proxy import ProxyItemDB
from app.services.proxy_service import ProxyService


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


async def _create_user(session: AsyncSession) -> User:
    user = User(
        telegram_id="12345",
        chat_id="chat",
        username="username",
        firstname="First",
        language="en",
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _build_proxy_item(
    user_id: int,
    *,
    auto_prolong: bool,
    date_end: datetime,
) -> ProxyItemDB:
    date_start = date_end - timedelta(days=1)
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
        date=date_start,
        date_end=date_end,
        unixtime=int(date_start.timestamp()),
        unixtime_end=int(date_end.timestamp()),
        descr="test proxy",
        active=True,
        provider="provider",
        auto_prolong=auto_prolong,
        days=1,
        login_proxy="user",
        pass_proxy="pass",
    )


def _normalize_expected_time(when: datetime) -> datetime:
    if when.tzinfo is None:
        return when
    return when.astimezone(timezone.utc).replace(tzinfo=None)


@pytest.mark.asyncio
async def test_create_proxy_schedules_expiring_notification_at_expected_time(
    async_session: AsyncSession,
) -> None:
    user = await _create_user(async_session)
    service = ProxyService(async_session)

    date_end = datetime(2025, 1, 2, 12, 30, tzinfo=timezone.utc)
    data = _build_proxy_item(user.id, auto_prolong=False, date_end=date_end)

    proxy = await service.create_proxy(data, notification=True)

    result = await async_session.execute(Notification.__table__.select())
    rows = result.fetchall()
    assert len(rows) == 1

    row = rows[0]
    assert row.user_id == user.id
    assert row.type == NotificationType.proxy_expiring
    assert row.sent is False

    notify_at = proxy.date_end - timedelta(hours=6)
    expected_scheduled_at = _normalize_expected_time(notify_at)
    assert row.scheduled_at == expected_scheduled_at

    payload = json.loads(row.payload)
    assert payload["proxy_id"] == proxy.id
    assert payload["host"] == f"{data.host}:{data.port}"
    assert payload["expires_at"] == proxy.date_end.isoformat()
