from app.models.balance import Balance
from sqlalchemy.ext.asyncio import AsyncSession

async def create_balance(user_id: int, session: AsyncSession):
    balance = Balance(user_id=user_id, amount=0.0)
    session.add(balance)
    await session.flush()
    await session.commit()
    return balance