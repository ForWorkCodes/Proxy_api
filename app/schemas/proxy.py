from pydantic import BaseModel, Field
from typing import List
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
    port: int
    type: str
    country: str
    date_end: datetime


class ProxyBuyResponse(BaseModel):
    status: str
    proxies: List[ProxyItem]


class ProxyItemDB(BaseModel):
    user_id: int
    proxy_id: str
    ip: str
    transaction_id: int
    host: str
    port: int
    type: str
    country: str
    date: datetime
    date_end: datetime
    unixtime: int
    unixtime_end: int
    descr: str
    active: bool
