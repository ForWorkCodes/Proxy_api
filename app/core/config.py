from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Proxy API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "API for proxy management and monitoring"
    POSTGRES_DSN: str = "postgresql+asyncpg://postgres:postgres@localhost:port/postgres"
    API_SECRET: str = "supersecrettoken123"
    PROXY_API_KEY: str = "proxy"
    PROXY_API_URL: str = "https://proxy.site"
    CRYPTO_API_KEY_NOW_PAY: str = "***"
    CRYPTOCLOUD_API_KEY: str = "***"
    CRYPTOCLOUD_SHOP_ID: str = "***"
    INTERNAL_API_TOKEN: str = "super - secret - token"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True
    )


settings = Settings()
