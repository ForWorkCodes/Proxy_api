import json
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.sync_db import Base
from app.models.notification import Notification, NotificationType
from app.models.user import User
from app.services.notification_service import NotificationService


class DummyTelegramService:
    def __init__(self) -> None:
        self.messages: list[tuple[str, dict]] = []

    async def send_message(self, user_id: str, data: dict) -> bool:
        self.messages.append((user_id, data))
        return True


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


async def _create_user(session: AsyncSession, *, notifications_enabled: bool = True) -> User:
    user = User(
        telegram_id="123456",
        chat_id="chat",
        username="tester",
        firstname="Tester",
        language="en",
        notification=notifications_enabled,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_schedule_notification_deduplicate(async_session: AsyncSession) -> None:
    user = await _create_user(async_session)
    service = NotificationService(async_session, telegram_service=DummyTelegramService())

    when = datetime.now(timezone.utc)
    payload = {"proxy_id": 1}

    first = await service.schedule_notification(
        user.id,
        NotificationType.proxy_expiring,
        when,
        payload,
        deduplicate=True,
    )

    duplicate = await service.schedule_notification(
        user.id,
        NotificationType.proxy_expiring,
        when,
        payload,
        deduplicate=True,
    )

    assert first is not None
    assert duplicate is None

    stmt = await async_session.execute(
        Notification.__table__.select()
    )
    rows = stmt.fetchall()
    assert len(rows) == 1
    assert json.loads(rows[0].payload) == payload


@pytest.mark.asyncio
async def test_process_pending_sends_notifications(async_session: AsyncSession) -> None:
    user = await _create_user(async_session)
    dummy = DummyTelegramService()
    service = NotificationService(async_session, telegram_service=dummy)

    await service.schedule_notification(
        user.id,
        NotificationType.proxy_expiring,
        datetime.now(timezone.utc) - timedelta(minutes=1),
        {"proxy_id": 2},
    )

    delivered = await service.process_pending()

    assert delivered == 1
    assert len(dummy.messages) == 1
    telegram_id, message = dummy.messages[0]
    assert telegram_id == user.telegram_id
    assert message["type"] == NotificationType.proxy_expiring.value
    assert message["data"]["proxy_id"] == 2
    assert message["language"] == user.language

    stmt = await async_session.execute(Notification.__table__.select())
    rows = stmt.fetchall()
    assert rows[0].sent is True
    assert rows[0].sent_at is not None


@pytest.mark.asyncio
async def test_process_pending_skips_when_notifications_disabled(async_session: AsyncSession) -> None:
    user = await _create_user(async_session, notifications_enabled=False)
    dummy = DummyTelegramService()
    service = NotificationService(async_session, telegram_service=dummy)

    await service.schedule_notification(
        user.id,
        NotificationType.proxy_expiring,
        datetime.now(timezone.utc),
        {},
    )

    delivered = await service.process_pending()

    assert delivered == 0
    assert dummy.messages == []

    stmt = await async_session.execute(Notification.__table__.select())
    rows = stmt.fetchall()
    assert rows[0].sent is True
