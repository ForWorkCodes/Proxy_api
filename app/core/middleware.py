from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from app.core.config import settings


class InternalAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        open_paths = ["/docs", "/openapi.json", "/redoc", "/static"]
        if any(request.url.path.startswith(path) for path in open_paths):
            return await call_next(request)

        token = request.headers.get("X-Internal-Token")
        if not token or token.strip() != settings.INTERNAL_API_TOKEN.strip():
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized. Invalid or missing token."}
            )

        return await call_next(request)
