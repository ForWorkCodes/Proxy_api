from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.user import UserCreate, UserOut, UserLangUpdate
from app.models.user import User
from app.core.db import get_async_session
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from app.services.user_registration import upsert_user_with_balance
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/user/by-telegram-id/{telegram_id}", response_model=UserOut)
async def get_user_by_telegram_id(telegram_id: str, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(
        select(User)
        .options(selectinload(User.balance))
        .where(User.telegram_id == telegram_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        return {
            "success": False,
            "status_code": 404,
            "error": "User not found"
        }
    
    return user


@router.post("/user/upsert", response_model=UserOut | None)
async def upsert_user(data: UserCreate, session: AsyncSession = Depends(get_async_session)):
    user = await upsert_user_with_balance(data, session)
    return UserOut(**user.__dict__)


@router.patch("/user/{telegram_id}/language")
async def update_language(telegram_id: str, data: UserLangUpdate, session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.language = data.language
    user.updated_at = datetime.now(timezone.utc)
    await session.commit()
    return {"status": "updated"}
