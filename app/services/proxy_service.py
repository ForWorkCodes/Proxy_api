from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.proxy import ProxyItemDB
from app.models.user import User
from app.models.proxy import Proxy
from datetime import datetime


class ProxyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_list_proxy(self, user: User, transaction_id: int, data_from_api: dict):
        proxy_list = data_from_api.get("list", {})
        results = []

        for proxy_id, proxy_data in proxy_list.items():
            try:
                item = ProxyItemDB(
                    user_id=user.id,
                    proxy_id=proxy_id,
                    ip=proxy_data["ip"],
                    transaction_id=transaction_id,
                    host=proxy_data["host"],
                    port=proxy_data["port"],
                    type=proxy_data["type"],
                    country=proxy_data["descr"].split(":")[-1] if proxy_data.get("descr") else None,
                    date=datetime.strptime(proxy_data["date"], "%Y-%m-%d %H:%M:%S"),
                    date_end=datetime.strptime(proxy_data["date_end"], "%Y-%m-%d %H:%M:%S"),
                    unixtime=proxy_data["unixtime"],
                    unixtime_end=proxy_data["unixtime_end"],
                    descr=proxy_data.get("descr", ""),
                    active=True
                )

                proxy_obj = await self.create_proxy(item)
                results.append({"proxy_id": proxy_id, "success": True})
            except Exception as e:
                results.append({"proxy_id": proxy_id, "success": False, "error": str(e)})

        return {
            "success": all(r["success"] for r in results),
            "proxies": results
        }

    async def create_proxy(self, data: ProxyItemDB):
        proxy = Proxy(
            user_id=data.user_id,
            proxy_id=data.proxy_id,
            ip=data.ip,
            transaction_ip=data.transaction_ip,
            host=data.host,
            port=data.port,
            type=data.type,
            country=data.country,
            date=data.date,
            date_end=data.date_end,
            unixtime=data.unixtime,
            unixtime_end=data.unixtime_end,
            descr=data.descr,
            active=data.active
        )
        self.session.add(proxy)
        await self.session.commit()

        return proxy

    async def get_list_proxy_by_user(self, user_id: int):
        print("da")
