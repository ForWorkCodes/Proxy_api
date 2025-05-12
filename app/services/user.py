from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.schemas.user import UserCreate
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone


async def get_user_by_telegram_id(telegram_id: str, session: AsyncSession) -> User | None:
    result = await session.execute(select(User).options(selectinload(User.balance)).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


async def upsert_user(data: UserCreate, session: AsyncSession) -> User:
    user = await get_user_by_telegram_id(data.telegram_id, session)

    if user:
        user.username = data.username
        user.firstname = data.firstname
        user.language = data.language
        user.telegram_id = data.telegram_id
        user.active = data.active
        user.banned = data.banned
        user.chat_id = data.chat_id
    else:
        user = User(**data.model_dump())
        session.add(user)

    await session.flush()
    await session.commit()

    await session.refresh(user, attribute_names=["balance"])
    
    return user
