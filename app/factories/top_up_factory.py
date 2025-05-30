from app.strategies.nowpayments_strategy import NowPaymentsStrategy
from app.strategies.cryptocloud_strategy import CryptoCloudStrategy
from app.interfaces.top_up_strategy import TopUpStrategy


class TopUpStrategyFactory:
    @staticmethod
    def get_strategy(provider_name: str) -> TopUpStrategy | None:
        if provider_name == "cryptocloud":
            return CryptoCloudStrategy()
        elif provider_name == "newpayment":
            return NowPaymentsStrategy()
        raise ValueError(f"Unsupported provider: {provider_name}")
