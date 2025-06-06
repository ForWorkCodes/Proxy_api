import sys
import os
import pytest
from unittest.mock import AsyncMock, patch
from app.orchestrators.proxy import BuyProxyOrchestrator
from app.schemas.proxy import ProxyBuyRequest, ProxyItem
from app.services.proxy_service import ProxyService
from datetime import datetime
from typing import List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))


@pytest.mark.asyncio
async def test_successful_buy_proxy():
    session = AsyncMock()

    request = ProxyBuyRequest(
        telegram_id="123",
        version="4",
        type="https",
        country="us",
        days=30,
        quantity=1,
        auto_prolong=False
    )

    with patch("app.orchestrators.proxy.buy_proxy.UserService") as mock_user_service, \
         patch("app.orchestrators.proxy.buy_proxy.BalanceService") as mock_balance_service, \
         patch("app.orchestrators.proxy.buy_proxy.TransactionService") as mock_transaction_service, \
         patch("app.orchestrators.proxy.buy_proxy.ProxyApiService") as mock_proxy_api, \
         patch("app.orchestrators.proxy.buy_proxy.ProxyService") as mock_proxy_service:

        # Пользователь и баланс
        mock_user = AsyncMock()
        mock_user.id = 1
        mock_user.balance.amount = 100.0
        mock_user_service.return_value.get_user_by_telegram_id = AsyncMock(return_value=mock_user)

        # Баланс
        mock_balance_service.return_value.check_balance = AsyncMock(return_value={"success": True})
        mock_balance_service.return_value.check_minus_balance.return_value = 90.0
        mock_balance_service.return_value.check_plus_balance.return_value = 100.0
        mock_balance_service.return_value.subtract_money = AsyncMock(return_value={"success": True})
        mock_balance_service.return_value.add_money = AsyncMock(return_value={"success": True})

        # Транзакции
        mock_transaction_service.return_value.create_wait_proxy_transaction = AsyncMock(return_value={
            "success": True,
            "transaction_id": 42
        })
        mock_transaction_service.return_value.create_refund_transaction = AsyncMock(return_value={
            "success": True,
            "transaction_id": 43
        })
        mock_transaction_service.return_value.update_status = AsyncMock()

        # API
        mock_proxy_api.return_value.get_proxy_price = AsyncMock(return_value={
            "success": True,
            "total_price": 10.0
        })
        mock_proxy_api.return_value.buy_proxy = AsyncMock(return_value={
            "success": True,
            "data": {
                "list": {
                    "proxy1": {
                        "ip": "1.2.3.4",
                        "host": "host",
                        "port": 8080,
                        "version": 4,
                        "type": "https",
                        "country": "us",
                        "date": "2024-01-01 00:00:00",
                        "date_end": "2024-02-01 00:00:00",
                        "unixtime": 1704067200,
                        "unixtime_end": 1706745600,
                        "active": True,
                        "descr": "desc"
                    }
                },
                "period": 30,
                "country": "us"
            }
        })

        # ProxyService
        mock_proxy_item_list: List[ProxyItem] = []
        mock_proxy_item_list.append(ProxyItem(
            ip="1.2.3.4",
            host="host",
            port=8080,
            version=4,
            type="https",
            country="us",
            date=datetime.strptime("2024-01-01 00:00:00", "%Y-%m-%d %H:%M:%S"),
            date_end=datetime.strptime("2024-02-01 00:00:00", "%Y-%m-%d %H:%M:%S"),
            unixtime=1704067200,
            unixtime_end=1706745600,
            descr="desc",
            active=True,
            auto_prolong=False
        ))
        mock_proxy_service.return_value.create_list_proxy = AsyncMock(return_value={
            "success": True,
            "quantity": 1,
            "days": 30,
            "country": "us",
            "proxies": mock_proxy_item_list
        })

        real_proxy_service = ProxyService(session=AsyncMock())
        mock_proxy_service.return_value.to_proxy_item_response.side_effect = real_proxy_service.to_proxy_item_response

        orchestrator = BuyProxyOrchestrator(session)
        result = await orchestrator.execute(request)

        assert result.success is True
        assert result.status_code == 200
