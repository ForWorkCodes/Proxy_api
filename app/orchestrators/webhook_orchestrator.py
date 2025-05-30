from sqlalchemy.ext.asyncio import AsyncSession
from app.services.user_service import UserService
from app.services.balance_service import BalanceService
from app.services.transaction_service import TransactionService
import logging

logger = logging.getLogger(__name__)


class WebhookOrchestrator:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_service = UserService(session)
        self.balance_service = BalanceService(session)
        self.transaction_service = TransactionService(session)

    async def execute(self, data: dict):
        external_id = data["invoice_id"]
        transaction = await self.transaction_service.get_transaction_by_external_id(str(external_id))
        if not transaction:
            logger.error(
                f"[TRANSACTION FAILED] Could not found transaction by external_id: {external_id}")
            return {"status": "error"}

        if data["status"] == "failed" and transaction.status != "failed":
            await self.transaction_service.update_status(transaction.id, "failed", "Top Up failed")
            logger.error(
                f"[TRANSACTION FAILED] Status for transaction is failed by external_id: {external_id}")
            return {"status": "error"}
        elif data["status"] == "cancelled" and transaction.status != "cancelled":
            await self.transaction_service.update_status(transaction.id, "cancelled", "Top Up cancelled")
            logger.error(
                f"[TRANSACTION FAILED] Status for transaction is cancelled by external_id: {external_id}")
            return {"status": "error"}

        if data["status"] != "success":
            logger.error(
                f"[TRANSACTION FAILED] Status for transaction is not success by external_id: {external_id}")
            return {"status": "error"}
        if transaction.status == "success":
            logger.error(
                f"[TRANSACTION FAILED] Status for local transaction is success by external_id: {external_id}")
            return {"status": "error"}

        user_id = transaction.user_id
        user = await self.user_service.get_user_by_id(user_id)

        if not user:
            logger.error(
                f"[TRANSACTION FAILED] Could not found user for transaction external_id: {external_id}")
            await self.transaction_service.update_status(transaction.id, "failed", "Can't found user: " + user_id)
            return {"status": "error"}

        result_money = await self.balance_service.add_money(user, float(transaction.amount))
        if not result_money["success"]:
            await self.transaction_service.update_status(transaction.id, "failed", "Top Up successful but we can't add money")

        await self.transaction_service.update_status(transaction.id, "success", "Top Up successful. New balance: " +
                                                     result_money["new_balance"])

        return {"status": "ok"}
