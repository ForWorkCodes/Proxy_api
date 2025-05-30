from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_service import UserService
from app.services.balance_service import BalanceService
from app.services.transaction_service import TransactionService


class WebhookOrchestrator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(session)
        self.balance_service = BalanceService(session)
        self.transaction_service = TransactionService(session)

    async def execute(self, data: dict):
        user = await self.user_service.get_user_by_telegram_id(data["telegram_id"])
        amount = data["amount"]
        new_balance = self.balance_service.check_plus_balance(user, amount)

        #await self.transaction_service.create_topup_transaction(user, amount, new_balance, data["txid"], data["comment"])
        await self.balance_service.add_money(user, amount)
