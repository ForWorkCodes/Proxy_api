from sqlalchemy.ext.asyncio import AsyncSession
from app.models.transaction import Transaction
from app.services import BalanceService
from app.models.user import User
from sqlalchemy import select


class TransactionService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.balance_service = BalanceService(self.session)

    async def create_refund_transaction(self, user: User, amount: float, new_balance: float, related_ids: str | None):
        if not user or not user.balance:
            return {
                "success": False,
                "status_code": 404,
                "error": "User or balance not found"
            }

        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            balance_after=new_balance,
            related_ids=related_ids,
            type="refund",
            status="paid",
            comment=f"Refund for user {user.id}"
        )

        self.session.add(transaction)
        await self.session.commit()

        if transaction.id is not None:
            return {
                "success": True,
                "status_code": 200,
                "transaction_id": transaction.id
            }
        else:
            return {
                "success": False,
                "status_code": 404,
                "error": "Transaction was not created"
            }

    async def create_wait_proxy_transaction(self, user: User, amount: float, new_balance: float) -> dict:
        if not user or not user.balance:
            return {
                "success": False,
                "status_code": 404,
                "error": "User or balance not found"
            }

        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            balance_after=new_balance,
            type="proxy",
            status="pending",
            comment=f"Buy proxies for user {user.id}"
        )

        self.session.add(transaction)
        await self.session.commit()

        if transaction.id is not None:
            return {
                "success": True,
                "status_code": 200,
                "transaction_id": transaction.id
            }
        else:
            return {
                "success": False,
                "status_code": 404,
                "error": "Transaction was not created"
            }

    async def create_wait_top_up_transaction(self, user: User, amount: float, new_balance: float, provider_name: str):
        if not user or not user.balance:
            return {
                "success": False,
                "status_code": 404,
                "error": "User or balance not found"
            }

        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            balance_after=new_balance,
            provider=provider_name,
            type="topup",
            status="pending",
            comment=f"Top up by user {user.id}"
        )

        self.session.add(transaction)
        await self.session.commit()

        if transaction.id is not None:
            return {
                "success": True,
                "status_code": 200,
                "transaction_id": transaction.id
            }
        else:
            return {
                "success": False,
                "status_code": 404,
                "error": "Transaction was not created"
            }

    async def update_status(self, transaction_id: int, status: str, comment):
        transaction = await self.session.get(Transaction, transaction_id)
        if transaction:
            transaction.status = status
            transaction.comment += " | " + comment
            await self.session.commit()

    async def update_external_id(self, transaction_id: int, external_id: str):
        transaction = await self.session.get(Transaction, transaction_id)
        if transaction:
            transaction.external_id = external_id
            await self.session.commit()

    async def get_transaction_by_external_id(self, external_id: str) -> Transaction | None:
        raw = await self.session.execute(select(Transaction).where(Transaction.external_id == external_id))
        transaction = raw.scalar_one_or_none()

        return transaction
