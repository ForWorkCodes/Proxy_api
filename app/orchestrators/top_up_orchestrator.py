from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_service import UserService
from app.services.balance_service import BalanceService
from app.services.transaction_service import TransactionService
from app.factories.top_up_factory import TopUpStrategyFactory
import logging

logger = logging.getLogger(__name__)


class TopUpOrchestrator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(self.session)
        self.transaction_service = TransactionService(self.session)
        self.balance_service = BalanceService(session)

    async def execute(self, telegram_id: str, provider_key: str, amount: float):
        user = await self.user_service.get_user_by_telegram_id(telegram_id)
        if not user or not user.balance:
            logger.warning(f"[USER FAILED] User or balance not found for telegram_id={telegram_id}")
            return {
                "success": False,
                "status_code": 404,
                "topup_url": "",
                "error": "User or balance not found"
            }

        new_balance = self.balance_service.check_plus_balance(user, amount)

        transaction_status = await self.transaction_service.create_wait_top_up_transaction(user, amount, new_balance)
        if not transaction_status["success"]:
            logger.error(
                f"[TRANSACTION FAILED] Could not create pending transaction: {transaction_status.get('error')}")
            return transaction_status

        transaction_id = transaction_status["transaction_id"]
        logger.info(f"[TRANSACTION CREATED] ID={transaction_id}, amount={amount}, new_balance={new_balance}")

        strategy = TopUpStrategyFactory.get_strategy(provider_key)
        response = await strategy.generate_link(user, amount, transaction_id)

        if not response['success']:
            await self.transaction_service.update_status(transaction_id, "failed", response['error'])
            logger.error(f"[TRANSACTION FAILED] Could not create pending transaction: {response['error']}")

        await self.transaction_service.update_external_id(transaction_id, response['invoice_id'])

        return {
            "success": response['success'],
            "status_code": 200,
            "topup_url": response['link'],
            "error": response['error']
        }
