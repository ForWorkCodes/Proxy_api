from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.proxy import ProxyBuyRequest, ProxyBuyResponse
from app.services import ProxyApiService, BalanceService, TransactionService, ProxyService, UserService
import logging

logger = logging.getLogger(__name__)


class BuyProxyOrchestrator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(self.session)
        self.proxy_api = ProxyApiService(self.session)
        self.balance_service = BalanceService(self.session)
        self.transaction_service = TransactionService(self.session)
        self.proxy_service = ProxyService(self.session)

    async def execute(self, request: ProxyBuyRequest):
        logger.info(
            f"[BUY START] Request received from telegram_id={request.telegram_id} for {request.quantity} proxies ({request.version}/{request.type}) for {request.days} days in {request.country}")

        # Getting actual price for proxy
        data_price = await self.proxy_api.get_proxy_price(request.version, request.quantity,
                                                          request.days, request.telegram_id)
        if not data_price['success']:
            logger.warning(f"[PRICE FAILED] Could not get price: {data_price.get('error')}")
            return data_price

        price = data_price["total_price"]
        logger.info(f"[PRICE OK] Total price calculated: {price}")

        # Getting current user
        user = await self.user_service.get_user_by_telegram_id(request.telegram_id)
        if not user or not user.balance:
            logger.warning(f"[USER FAILED] User or balance not found for telegram_id={request.telegram_id}")
            return {
                "success": False,
                "status_code": 404,
                "error": "User or balance not found"
            }

        logger.info(f"[USER OK] User ID: {user.id}, Current balance: {user.balance.amount}")

        # Checking users balance for price
        have_money = await self.balance_service.check_balance(user, price)
        if not have_money["success"]:
            logger.warning(f"[BALANCE CHECK FAILED] {have_money.get('error')}")
            return have_money

        logger.info(f"[BALANCE OK] User has enough balance")

        # Create first step of Transaction
        new_balance = self.balance_service.check_minus_balance(user, price)
        transaction_status = await self.transaction_service.create_wait_proxy_transaction(user, price, new_balance)
        if not transaction_status["success"]:
            logger.error(
                f"[TRANSACTION FAILED] Could not create pending transaction: {transaction_status.get('error')}")
            return transaction_status

        transaction_id = transaction_status["transaction_id"]
        logger.info(f"[TRANSACTION CREATED] ID={transaction_id}, amount={price}, new_balance={new_balance}")

        # Subtract money
        subtract_money = await self.balance_service.subtract_money(user, price)
        if not subtract_money["success"]:
            await self.transaction_service.update_status(transaction_id, "failed", subtract_money["error"])
            logger.error(f"[SUBTRACT FAILED] {subtract_money.get('error')}")
            return subtract_money

        logger.info(f"[SUBTRACT OK] {price} deducted from user ID={user.id}")

        # Send request to the api
        buying_status = await self.proxy_api.buy_proxy(
            request.version, request.quantity,
            request.days, request.country, request.type, request.telegram_id
        )

        if not buying_status["success"] or not buying_status["data"]:
            comment = "Purchase failed: " + buying_status.get("error", "Unknown")
            logger.error(f"[BUYING FAILED] {comment}")
            await self.transaction_service.update_status(transaction_id, "failed", comment)

            # Returning money
            new_balance = self.balance_service.check_plus_balance(user, price)
            transaction_refund = await self.transaction_service.create_refund_transaction(user, price, new_balance, str(transaction_id))
            await self.balance_service.add_money(user, price)

            logger.info(f"[REFUND] Returned {price} to user ID={user.id}, balance restored to {new_balance}")
            return buying_status

        logger.info(f"[BUYING OK] Proxy API returned {len(buying_status['data'].get('list', {}))} proxies")

        # Creating proxy for user
        result = await self.proxy_service.create_list_proxy(user, transaction_id, buying_status["data"])
        logger.info(f"[SAVE OK] proxies saved to DB for user ID={user.id}")

        # Update Transaction status
        comment = "Purchase complete"
        await self.transaction_service.update_status(transaction_id, "completed", comment)
        logger.info(f"[TRANSACTION COMPLETED] ID={transaction_id}")

        proxy_dicts = [self.proxy_service.to_proxy_item_response(p).model_dump() for p in result["proxies"]]

        result = ProxyBuyResponse(
            success=True,
            status_code=200,
            error="",
            quantity=result["quantity"],
            price=price,
            days=result["days"],
            country=result["country"],
            proxies=proxy_dicts
        )
        return result
