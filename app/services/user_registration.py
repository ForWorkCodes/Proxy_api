from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user import upsert_user
from app.services.balance import create_balance
from app.schemas.user import UserCreate
from app.models.user import User


async def upsert_user_with_balance(data: UserCreate, session: AsyncSession) -> User:
    try:
        user = await upsert_user(data, session)
        if not user.balance:
            await create_balance(user.id, session)
        return user
    except Exception as e:
        await session.rollback()
        raise e
