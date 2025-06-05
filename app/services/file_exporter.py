from sqlalchemy.ext.asyncio import AsyncSession
import csv
from typing import List
from openpyxl import Workbook
from app.models import Proxy
from app.core.constants import REVERSE_PROXY_TYPE_MAPPING, COUNTRY_TRANSLATIONS

COLUMN_TITLES = {
    "en": ["Version", "Ip:Port", "Type", "Country", "Date End"],
    "ru": ["Версия", "Ip:Порт", "Тип", "Страна", "Дата окончания"],
}

class FileExporter:
    def __init__(self, session: AsyncSession):
        self.session = session

    def export_proxies_to_csv(self, filepath: str, proxies: List[Proxy], lang: str) -> None:
        with open(filepath, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(COLUMN_TITLES[lang])
            for proxy in proxies:
                country = COUNTRY_TRANSLATIONS.get(lang, {}).get(proxy.country, proxy.country.upper())
                writer.writerow([
                    REVERSE_PROXY_TYPE_MAPPING.get(str(proxy.version), "unknown"),
                    f"{proxy.host}:{proxy.port}",
                    proxy.type,
                    country,
                    proxy.date_end.strftime("%Y-%m-%d %H:%M") if proxy.date_end else ""
                ])

    def export_proxies_to_xls(self, filepath: str, proxies: List[Proxy], lang: str) -> None:
        wb = Workbook()
        ws = wb.active
        ws.append(COLUMN_TITLES[lang])
        for proxy in proxies:
            country = COUNTRY_TRANSLATIONS.get(lang, {}).get(proxy.country, proxy.country.upper())
            ws.append([
                REVERSE_PROXY_TYPE_MAPPING.get(str(proxy.version), "unknown"),
                f"{proxy.host}:{proxy.port}",
                proxy.type,
                country,
                proxy.date_end.strftime("%Y-%m-%d %H:%M") if proxy.date_end else ""
            ])
        wb.save(filepath)
