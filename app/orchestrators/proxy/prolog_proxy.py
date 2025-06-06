from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from app.models.proxy import Proxy
from app.models.user import User
from app.services import ProxyApiService, BalanceService, TransactionService, ProxyService, UserService
import logging

logger = logging.getLogger(__name__)


class PrologProxyOrchestrator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(self.session)
        self.proxy_api = ProxyApiService(self.session)
        self.balance_service = BalanceService(self.session)
        self.transaction_service = TransactionService(self.session)
        self.proxy_service = ProxyService(self.session)

    async def execute(self):
        logger.info(f"[Prolog Proxy START]")
        now = datetime.now(timezone.utc).timestamp()
        deadline = now + 4500

        expiring = await self.proxy_service.get_proxies_to_auto_prolong(deadline)
        if not expiring:
            print("[CRON] No proxies found")
            logger.info("[CRON] No proxies found")
            return

        user_cache = {}  # user_id -> User
        results = []

        for proxy in expiring:
            try:
                result = await self._process_proxy(proxy, user_cache)
                results.append(result)
            except Exception as e:
                logger.exception(f"[Prolog EXCEPTION] Proxy ID={proxy.id}, Error: {e}")
                results.append(False)

        logger.info(
            f"[Prolog FINISHED] Total={len(expiring)}, Success={results.count(True)}, Failed={results.count(False)}")

    async def _process_proxy(self, proxy: Proxy, user_cache: dict[int, User]) -> bool:
        # Getting current user for cache or db
        user = user_cache.get(proxy.user_id)
        if not user:
            logger.info(f"[Prolong USER CACHE NOT FOUND] user_id={proxy.user_id}")
            user = await self.user_service.get_user_by_id(proxy.user_id)
            if not user:
                logger.warning(f"[Prolong USER NOT FOUND] user_id={proxy.user_id}")
                return False
            user_cache[proxy.user_id] = user
        else:
            logger.info(f"[Prolong USER CACHE FOUND] user_id={proxy.user_id}")

        # Getting actual price for proxy
        price_info = await self.proxy_api.get_proxy_price(str(proxy.version), 1, proxy.days, user.id, False)
        if not price_info["success"]:
            logger.warning(f"[Prolong PRICE FAILED] Proxy ID={proxy.id}, Error={price_info.get('error')}")
            return False

        price = price_info["total_price"]
        logger.info(f"[Prolong PRICE OK] Proxy ID={proxy.id}, Price={price}")

        # Checking users balance for price
        balance_check = await self.balance_service.check_balance(user, price)
        if not balance_check["success"]:
            logger.warning(f"[Prolog BALANCE FAIL] user_id={user.id}, Error={balance_check['error']}")
            return False
        logger.info(f"[Prolong BALANCE OK] User has enough balance")

        # Create first step of Transaction
        new_balance = balance_check["amount"]
        transaction = await self.transaction_service.create_prolong_proxy_transaction(user, price, new_balance, proxy.id,
                                                                                     proxy.provider)

        if not transaction["success"]:
            logger.error(f"[Prolong TRANSACTION FAIL] Proxy ID={proxy.id}, Error={transaction['error']}")
            return False

        transaction_id = transaction["transaction_id"]
        logger.info(f"[Prolong TRANSACTION OK] Transaction ID={transaction_id}")

        # Subtract money
        subtract_money = await self.balance_service.subtract_money(user, price)
        if not subtract_money["success"]:
            await self.transaction_service.update_status(transaction_id, "failed", subtract_money["error"])
            logger.error(f"[Prolog SUBTRACT FAIL] Proxy ID={proxy.id}, Error={subtract_money['error']}")
            return False

        logger.info(f"[Prolong SUBTRACT OK] User ID={user.id}, Amount={price}")

        # Buying
        prolong_data = {
            "id": proxy.proxy_id,
            "period": proxy.days
        }
        buying_status = await self.proxy_api.try_prolong_proxy(prolong_data)
        if not buying_status["success"] or not buying_status.get("data"):
            reason = buying_status.get("error", "Unknown error")
            logger.error(f"[Prolong BUYING FAIL] Proxy ID={proxy.id}, Reason: {reason}")
            await self.transaction_service.update_status(transaction_id, "failed", reason)

            # Returning money
            new_balance = await self.balance_service.add_money(user, price)
            await self.transaction_service.create_refund_transaction(
                user, price, new_balance["new_balance"], str(transaction_id))

            logger.info(f"[Prolong REFUND] Proxy ID={proxy.id}, Amount={price}, New Balance={new_balance['new_balance']}")
            return False

        logger.info(f"[Prolog BUYING OK] Proxy API returned {len(buying_status['data'].get('list', {}))} proxies")

        # Updating proxy expiring
        response_proxy = buying_status['data'].get('list', {})
        cur_proxy = response_proxy[str(proxy.proxy_id)]
        await self.proxy_service.update_expiring_date(proxy, cur_proxy)
        logger.info(f"[Prolong UPDATE OK] Proxy ID={proxy.id}, User ID={user.id} - array={cur_proxy}")

        # Update Transaction status
        await self.transaction_service.update_status(transaction_id, "completed", "Prolong complete")
        logger.info(f"[Prolong TRANSACTION COMPLETE] Transaction ID={transaction_id}")

        return True
