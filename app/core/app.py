from fastapi import FastAPI
from app.core.config import settings
from fastapi.staticfiles import StaticFiles
from app.core.middleware import InternalAuthMiddleware
from app.core.logging_config import setup_logging

setup_logging()

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description=settings.DESCRIPTION,
        version=settings.VERSION,
    )

    app.add_middleware(InternalAuthMiddleware)

    # Import and include routers
    from app.api.endpoints import system, debug, countries, user, proxy, webhook
    app.include_router(user.router, prefix=settings.API_V1_STR, tags=["User"])
    app.include_router(countries.router, prefix=settings.API_V1_STR, tags=["Proxy_api"])
    app.include_router(proxy.router, prefix=settings.API_V1_STR, tags=["Proxy_api"])
    app.include_router(system.router, prefix=settings.API_V1_STR, tags=["System"])
    app.include_router(debug.router, prefix=settings.API_V1_STR, tags=["Debug"])
    app.include_router(webhook.router, tags=["Webhook"])

    app.mount("/static", StaticFiles(directory="/tmp"), name="static")

    return app
