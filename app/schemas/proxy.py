from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime


class ProxyBuyRequest(BaseModel):
    telegram_id: str
    version: str
    type: str  # http, https, socks5
    country: str
    days: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


class ProxyItem(BaseModel):
    ip: str
    host: str
    port: int
    version: int
    type: str
    country: str
    date: datetime
    date_end: datetime
    unixtime: int
    unixtime_end: int
    descr: Optional[str] = None
    active: bool

    model_config = ConfigDict(from_attributes=True)


class ProxyItemResponse(BaseModel):
    ip: str
    host: str
    port: int
    version: str
    type: str
    country: str
    date: datetime
    date_end: datetime
    unixtime: int
    unixtime_end: int
    descr: Optional[str] = None
    active: bool

    model_config = ConfigDict(from_attributes=True)


class ProxyBuyResponse(BaseModel):
    success: bool
    status_code: int
    error: str
    quantity: int
    price: float
    days: int
    country: str
    proxies: List[ProxyItemResponse]


class ProxyItemDB(BaseModel):
    user_id: int
    proxy_id: str
    ip: str
    transaction_id: int
    host: str
    port: int
    version: int
    type: str
    country: str
    date: datetime
    date_end: datetime
    unixtime: int
    unixtime_end: int
    descr: str
    active: bool


class ProxyGetRequest(BaseModel):
    telegram_id: str


class ProxyCheckRequest(BaseModel):
    telegram_id: str
    address: str


class ProxyLinkRequest(BaseModel):
    telegram_id: str
    file_type: str