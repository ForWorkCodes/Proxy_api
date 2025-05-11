from fastapi import FastAPI
from app.core.config import settings

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
    )
    
    # Import and include routers
    from app.api.endpoints import system, debug, countries
    app.include_router(countries.router, prefix=settings.API_V1_STR, tags=["Proxy_api"])
    app.include_router(system.router, prefix=settings.API_V1_STR, tags=["System"])
    app.include_router(debug.router, prefix=settings.API_V1_STR, tags=["Debug"])
    
    return app 