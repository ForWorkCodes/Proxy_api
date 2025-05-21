from pydantic import BaseModel, ConfigDict, field_serializer
from typing import Optional
from datetime import datetime
from app.models.balance import Balance


class UserBase(BaseModel):
    telegram_id: str
    chat_id: Optional[str]
    username: Optional[str]
    firstname: Optional[str]
    language: str


class UserCreate(UserBase):
    pass


class UserOut(UserBase):
    id: int
    telegram_id: str
    username: Optional[str]
    firstname: Optional[str]
    language: str
    active: bool
    banned: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserLangUpdate(BaseModel):
    language: str
