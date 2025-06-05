from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.user import User
from app.schemas.user import UserCreate
from sqlalchemy.orm import selectinload


class UserService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).options(selectinload(User.balance)).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_telegram_id(self, telegram_id: str) -> User | None:
        result = await self.session.execute(select(User).options(selectinload(User.balance)).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def upsert_user(self, data: UserCreate) -> User:
        user = await self.get_user_by_telegram_id(data.telegram_id)

        if user:
            user.username = data.username
            user.firstname = data.firstname
            user.language = data.language
            user.telegram_id = data.telegram_id
            user.active = data.active
            user.banned = data.banned
            user.notification = data.notification
            user.chat_id = data.chat_id
        else:
            user = User(**data.model_dump())
            self.session.add(user)

        await self.session.flush()
        await self.session.commit()

        await self.session.refresh(user, attribute_names=["balance"])

        return user
