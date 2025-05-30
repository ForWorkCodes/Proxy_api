from abc import ABC, abstractmethod
from app.models import User


class TopUpStrategy(ABC):
    @abstractmethod
    async def generate_link(self, user: User, amount: float, transaction_id: int) -> dict:
        pass

    @abstractmethod
    async def process_callback(self, payload: dict) -> dict:
        """
        Обработка входящего колбека от платёжного провайдера.
        """
        pass
