import asyncio
import logging
from logging.handlers import RotatingFileHandler

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.currency_rate import CurrencyRate

# --- логирование критичных ошибок ---
critical_handler = RotatingFileHandler(
    "logs/currency_critical.log", maxBytes=1_000_000, backupCount=5
)
critical_handler.setLevel(logging.ERROR)
critical_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s'))
currency_critical_logger = logging.getLogger("currency_critical")
currency_critical_logger.setLevel(logging.ERROR)
currency_critical_logger.addHandler(critical_handler)
currency_critical_logger.propagate = False


class CurrencyProviderError(RuntimeError):
    pass


class CurrencyService:
    """
    Сервис получения курса RUB->USD.
    По умолчанию берём биржевой курс MOEX USDRUB_TOM (ближе к реальным сделкам в РФ),
    fallback — курс ЦБ РФ на дату.
    """

    _MOEX_URL_TEMPLATE = (
        "https://iss.moex.com/iss/engines/currency/markets/"
        "selt/boards/CETS/securities/{security}.json"
        "?iss.meta=off&iss.only=marketdata,securities"
    )
    _MOEX_SECURITIES = ("USDRUB_TOM", "USD000UTSTOM")
    _CBR_XML_URL = "https://www.cbr.ru/scripts/XML_daily.asp"  # официальный XML

    def __init__(self, session: AsyncSession, *, timeout=5.0, retries=2):
        self.session = session
        self._timeout = timeout
        self._retries = retries

    async def _http_get_json(self, url: str) -> dict:
        last_err = None
        for _ in range(self._retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    response = await client.get(url, headers={"Accept": "application/json, */*"})
                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if "xml" in content_type:
                        return {"__raw_xml__": response.text}
                    return response.json()
            except Exception as exc:
                last_err = exc
                await asyncio.sleep(0.2)
        raise CurrencyProviderError(f"GET failed: {url}: {last_err}")

    @staticmethod
    def _normalize_price_value(raw) -> float | None:
        if raw is None:
            return None
        if isinstance(raw, (int, float)):
            value = float(raw)
        elif isinstance(raw, str):
            raw = raw.strip().replace(",", ".")
            if not raw:
                return None
            try:
                value = float(raw)
            except ValueError:
                return None
        else:
            return None
        return value if value > 0 else None

    @classmethod
    def _parse_moex_payload(cls, payload: dict, security: str) -> float:
        """Extracts the security price from the MOEX JSON payload."""
        blocks = (
            ("marketdata", (
                "LAST", "LASTPRICE", "LCURRENTPRICE", "MARKETPRICE2", "MARKETPRICE3",
                "CLOSE", "LEGALCLOSEPRICE", "CLOSEPRICE", "OPEN", "HIGH", "LOW", "WAPRICE"
            )),
            ("securities", ("PREVADMITTEDQUOTE", "PREVLEGALCLOSEPRICE", "PREVPRICE")),
        )
        for block_name, keys in blocks:
            block = payload.get(block_name) or {}
            cols = block.get("columns") or block.get("COLUMNS")
            data = block.get("data") or []
            if not cols or not data:
                continue
            index_map = {key: cols.index(key) for key in keys if key in cols}
            if not index_map:
                continue
            sec_idx = cols.index("SECID") if "SECID" in cols else None
            for row in data:
                if sec_idx is not None and sec_idx < len(row):
                    sec_value = row[sec_idx]
                    if isinstance(sec_value, str) and sec_value != security:
                        continue
                for key, idx in index_map.items():
                    if idx >= len(row):
                        continue
                    value = cls._normalize_price_value(row[idx])
                    if value is not None:
                        return value
        raise CurrencyProviderError(f"MOEX: failed to extract price for {security}")

    @staticmethod
    def _parse_cbr_xml(xml_text: str) -> float:
        """
        Ищем <Valute ID="R01235"> ... <CharCode>USD</CharCode> ... <Value>83,1234</Value>
        Возвращаем RUB за 1 USD.
        """
        try:
            start = xml_text.find("<CharCode>USD</CharCode>")
            if start == -1:
                raise ValueError("USD not found")
            value_start = xml_text.find("<Value>", start)
            value_end = xml_text.find("</Value>", value_start)
            raw = xml_text[value_start + 7:value_end].strip()
            raw = raw.replace(",", ".")
            return float(raw)
        except Exception as exc:
            raise CurrencyProviderError(f"CBR parse error: {exc}")

    async def _rate_rub_per_usd_moex(self) -> float:
        last_err: CurrencyProviderError | None = None
        for security in self._MOEX_SECURITIES:
            url = self._MOEX_URL_TEMPLATE.format(security=security)
            try:
                payload = await self._http_get_json(url)
                return self._parse_moex_payload(payload, security)
            except CurrencyProviderError as exc:
                last_err = exc
                continue
        raise last_err or CurrencyProviderError("MOEX: all securities unavailable")

    async def _rate_rub_per_usd_cbr(self) -> float:
        data = await self._http_get_json(self._CBR_XML_URL)
        xml = data.get("__raw_xml__")
        if not xml:
            raise CurrencyProviderError("CBR: неожиданный формат")
        return self._parse_cbr_xml(xml)

    async def _fetch_rate_from_provider(self, provider: str) -> float:
        provider = provider.lower()
        if provider == "moex":
            return await self._rate_rub_per_usd_moex()
        if provider == "cbr":
            return await self._rate_rub_per_usd_cbr()
        raise CurrencyProviderError(f"unknown provider: {provider}")

    async def _get_latest_snapshot(
        self,
        *,
        provider: str,
        base_currency: str,
        quote_currency: str,
    ) -> CurrencyRate | None:
        stmt = (
            select(CurrencyRate)
            .where(
                CurrencyRate.provider == provider.lower(),
                CurrencyRate.base_currency == base_currency.upper(),
                CurrencyRate.quote_currency == quote_currency.upper(),
            )
            .order_by(CurrencyRate.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_currency_rate(
        self,
        provider: str = "moex",
        *,
        base_currency: str = "USD",
        quote_currency: str = "RUB",
    ) -> float:
        providers = [provider.lower()]
        if providers[0] != "moex":
            providers.append("moex")
        if "cbr" not in providers:
            providers.append("cbr")

        last_err: CurrencyProviderError | None = None
        for prov in providers:
            snapshot = await self._get_latest_snapshot(
                provider=prov,
                base_currency=base_currency,
                quote_currency=quote_currency,
            )
            if snapshot is None:
                last_err = CurrencyProviderError(f"no stored rate for provider {prov}")
                currency_critical_logger.error(f"rate provider {prov} failed: {last_err}")
                continue
            rate = snapshot.rate
            if not (10 <= rate <= 1000):
                last_err = CurrencyProviderError(f"suspicious rate {rate} from {prov}")
                currency_critical_logger.error(f"rate provider {prov} failed: {last_err}")
                continue
            return rate

        raise last_err or CurrencyProviderError(
            f"no stored rates for providers {providers}"
        )

    async def convert_price_rub_to_usd(
        self,
        rub_amount: float,
        *,
        provider: str = "moex",
    ) -> float:
        """
        Конвертация RUB -> USD по выбранному провайдеру (по умолчанию MOEX).
        """
        rate_rub_per_usd = await self.get_currency_rate(
            provider=provider,
            base_currency="USD",
            quote_currency="RUB",
        )
        print("=======================================================================================================")
        print("rate_rub_per_usd = " + str(rate_rub_per_usd))
        return rub_amount / rate_rub_per_usd

    async def convert_price(
        self,
        current_price_rub: float,
        *,
        provider: str = "moex",
    ) -> float:
        return await self.convert_price_rub_to_usd(current_price_rub, provider=provider)

    async def record_rate_snapshot(
        self,
        *,
        provider: str,
        rate_rub_per_usd: float,
        base_currency: str = "USD",
        quote_currency: str = "RUB",
    ) -> CurrencyRate:
        snapshot = CurrencyRate(
            provider=provider.lower(),
            base_currency=base_currency.upper(),
            quote_currency=quote_currency.upper(),
            rate=rate_rub_per_usd,
        )
        self.session.add(snapshot)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(snapshot)
        return snapshot

    async def fetch_and_record_rate(self, provider: str = "moex") -> CurrencyRate:
        providers = [provider.lower()]
        if providers[0] != "moex":
            providers.append("moex")
        if "cbr" not in providers:
            providers.append("cbr")

        last_err: CurrencyProviderError | None = None
        for prov in providers:
            try:
                rate = await self._fetch_rate_from_provider(prov)
                if not (10 <= rate <= 1000):
                    raise CurrencyProviderError(f"suspicious rate {rate} from {prov}")
                return await self.record_rate_snapshot(
                    provider=prov,
                    rate_rub_per_usd=rate,
                    base_currency="USD",
                    quote_currency="RUB",
                )
            except Exception as exc:
                last_err = CurrencyProviderError(str(exc))
                currency_critical_logger.error(f"rate provider {prov} failed: {exc}")
                continue

        raise last_err or CurrencyProviderError("all providers failed to fetch rate")
