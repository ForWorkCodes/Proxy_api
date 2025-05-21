from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


class BalanceService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_balance(self, user: User):
        if not user or not user.balance:
            return {
                "success": False,
                "status_code": 404,
                "error": "User or balance not found"
            }

        return {
            "success": True,
            "status_code": 200,
            "amount": user.balance.amount
        }

    async def check_balance(self, user: User, need_amount) -> dict:
        if not user or not user.balance:
            return {
                "success": False,
                "status_code": 404,
                "error": "User or balance not found"
            }
        else:
            balance = user.balance

        if balance.amount < need_amount:
            return {
                "success": False,
                "status_code": 4001,
                "error": "Insufficient balance"
            }

        return {
            "success": True,
            "status_code": 200,
            "error": ""
        }

    def check_minus_balance(self, user: User, new_amount: float):
        balance = user.balance.amount
        return balance - new_amount

    def check_plus_balance(self, user: User, new_amount: float):
        balance = user.balance.amount
        return balance + new_amount

    async def add_money(self, user: User, amount: float):
        if not user or not user.balance:
            return {
                "success": False,
                "status_code": 404,
                "error": "User or balance not found"
            }

        balance = user.balance
        balance.amount += amount
        await self.session.commit()

        return {
            "success": True,
            "status_code": 200,
            "new_balance": balance.amount
        }

    async def subtract_money(self, user: User, amount: float):
        if not user or not user.balance:
            return {
                "success": False,
                "status_code": 404,
                "error": "User or balance not found"
            }
        balance = user.balance

        if balance.amount < amount:
            return {
                "success": False,
                "status_code": 4001,
                "error": "Insufficient balance"
            }

        balance.amount -= amount
        await self.session.commit()

        return {
            "success": True,
            "status_code": 200,
            "new_balance": balance.amount
        }
