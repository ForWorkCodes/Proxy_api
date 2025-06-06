from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy import select, and_
from app.schemas.proxy import ProxyItemDB, ProxyItem, ProxyItemResponse, CreateProxyList
from app.models.notification import NotificationType
from app.models.user import User
from app.services.notification_service import NotificationService
from app.models.proxy import Proxy
from app.core.constants import REVERSE_PROXY_TYPE_MAPPING
from app.services.file_exporter import FileExporter
from datetime import datetime, timedelta, timezone
from typing import List
import logging
import os
from logging.handlers import RotatingFileHandler

logger = logging.getLogger(__name__)

critical_handler = RotatingFileHandler(
    "logs/proxy_critical.log",
    maxBytes=1_000_000,
    backupCount=5
)
critical_handler.setLevel(logging.ERROR)
critical_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] [%(levelname)s] %(message)s'
))

proxy_critical_logger = logging.getLogger("proxy_critical")
proxy_critical_logger.setLevel(logging.ERROR)
proxy_critical_logger.addHandler(critical_handler)
proxy_critical_logger.propagate = False


class ProxyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.notification_service = NotificationService(session)

    async def create_list_proxy(self, data: CreateProxyList):
        proxy_list = data.data_from_api.get("list", {})
        country = data.data_from_api.get("country")
        proxies: List[ProxyItem] = []

        for proxy_id, proxy_data in proxy_list.items():
            try:
                item = ProxyItemDB(
                    user_id=data.user.id,
                    proxy_id=proxy_id,
                    ip=proxy_data["ip"],
                    transaction_id=data.transaction_id,
                    host=proxy_data["host"],
                    port=proxy_data["port"],
                    version=proxy_data["version"],
                    type=proxy_data["type"],
                    country=country,
                    date=datetime.strptime(proxy_data["date"], "%Y-%m-%d %H:%M:%S"),
                    date_end=datetime.strptime(proxy_data["date_end"], "%Y-%m-%d %H:%M:%S"),
                    unixtime=proxy_data["unixtime"],
                    unixtime_end=proxy_data["unixtime_end"],
                    descr=proxy_data.get("descr", ""),
                    active=proxy_data["active"],
                    provider=data.provider,
                    auto_prolong=data.auto_prolong,
                    days=data.data_from_api.get("period")
                )

                await self.create_proxy(item, data.user.notification)

                proxies.append(ProxyItem(
                    ip=proxy_data["ip"],
                    host=proxy_data["host"],
                    port=proxy_data["port"],
                    version=proxy_data["version"],
                    type=proxy_data["type"],
                    country=country,
                    date=datetime.strptime(proxy_data["date"], "%Y-%m-%d %H:%M:%S"),
                    date_end=datetime.strptime(proxy_data["date_end"], "%Y-%m-%d %H:%M:%S"),
                    unixtime=proxy_data["unixtime"],
                    unixtime_end=proxy_data["unixtime_end"],
                    descr=proxy_data.get("descr", ""),
                    active=proxy_data["active"]
                ))
            except Exception as e:
                error_msg = {
                    "user_id": data.user.id,
                    "proxy_data": proxy_data,
                    "transaction_id": data.transaction_id,
                    "error": str(e)
                }
                proxy_critical_logger.error(f"[SAVE ERROR] Failed to save proxy: {error_msg}")

        return {
            "success": True,
            "quantity": len(proxy_list),
            "days": data.data_from_api.get("period"),
            "country": country,
            "proxies": proxies
        }

    async def create_proxy(self, data: ProxyItemDB, notification=True):
        proxy = Proxy(
            user_id=data.user_id,
            proxy_id=data.proxy_id,
            ip=data.ip,
            transaction_id=data.transaction_id,
            host=data.host,
            port=data.port,
            version=data.version,
            type=data.type,
            country=data.country,
            date=data.date,
            date_end=data.date_end,
            unixtime=data.unixtime,
            unixtime_end=data.unixtime_end,
            descr=data.descr,
            active=data.active,
            provider=data.provider,
            auto_prolong=data.auto_prolong,
            days=data.days
        )
        self.session.add(proxy)
        await self.session.commit()

        # move to orchestrator
        if notification and not data.auto_prolong:
            expires_at = proxy.date_end
            notify_at = expires_at - timedelta(hours=6)

            payload = {
                "type": NotificationType.proxy_expiring,
                "proxy_id": proxy.id,
                "host": data.host + ":" + str(data.port)
            }

            await self.notification_service.schedule_notification(
                data.user_id, NotificationType.proxy_expiring, notify_at, payload)

        return proxy

    async def get_list_proxy_by_user(self, user: User) -> List[Proxy]:
        db = select(Proxy).where(Proxy.user_id == user.id, Proxy.active)
        result = await self.session.execute(db)
        proxies: List[Proxy] = result.scalars().all()
        return proxies

    def to_proxy_item_response(self, item: ProxyItem) -> ProxyItemResponse:
        return ProxyItemResponse(
            **item.model_dump(exclude={"version"}),
            version=REVERSE_PROXY_TYPE_MAPPING.get(str(item.version), "unknown")
        )

    async def get_active_proxy_by_date(self, deadline: datetime) -> list[Proxy] | None:
        stmt = select(Proxy).where(
            Proxy.active,
            Proxy.date_end < deadline
        )

        result = await self.session.execute(stmt)
        proxies = result.scalars().all()
        return proxies if proxies else None

    async def get_proxies_to_auto_prolong(self, deadline) -> list[Proxy] | None:
        stmt = select(Proxy).where(
            Proxy.active.is_(True),
            Proxy.auto_prolong.is_(True),
            Proxy.unixtime_end <= deadline
        )

        result = await self.session.execute(stmt)
        proxies = result.scalars().all()
        return proxies if proxies else None

    async def update_expiring_date(self, proxy: Proxy, new_data: dict):
        proxy.unixtime_end = int(new_data["unixtime_end"])
        proxy.date_end = datetime.strptime(new_data["date_end"], "%Y-%m-%d %H:%M:%S")
        await self.session.commit()

    async def deactivate_proxy_list(self, proxies: list[Proxy]):
        for proxy in proxies:
            proxy.active = False
        await self.session.commit()

    async def get_proxy_by_telegram_ip_port(self, telegram_id: str, host: str, port: int) -> Proxy | None:
        stmt = (
            select(Proxy)
            .join(Proxy.owner)
            .options(joinedload(Proxy.owner))
            .where(
                and_(
                    Proxy.owner.has(User.telegram_id == telegram_id),
                    Proxy.host == host,
                    Proxy.port == port,
                    Proxy.active
                )
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def make_link_proxy_list(self, user: User, file_type: str) -> dict:
        proxies = await self.get_list_proxy_by_user(user)
        if not proxies:
            return {
                "success": False,
                "status_code": 2001,
                "error": "No proxies found"
            }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"proxies_{user.telegram_id}_{timestamp}.{file_type}"
        filepath = os.path.join("/tmp", filename)

        file_exporter = FileExporter(self.session)
        if file_type == "csv":
            file_exporter.export_proxies_to_csv(filepath, proxies, user.language)
        elif file_type == "xls":
            file_exporter.export_proxies_to_xls(filepath, proxies, user.language)
        else:
            return {
                "success": False,
                "status_code": 404,
                "error": "Invalid file type"
            }

        return {
            "success": True,
            "status_code": 200,
            "file_url": f"/static/{filename}"
        }
