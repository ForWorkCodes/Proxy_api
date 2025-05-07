from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Proxy API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "API for proxy management and monitoring"
    
    class Config:
        case_sensitive = True

settings = Settings() 