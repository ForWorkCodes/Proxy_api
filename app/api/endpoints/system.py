from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any
import platform
import sys
from app.core.config import settings

router = APIRouter()

@router.get("/", tags=["System"])
def root() -> Dict[str, str]:
    return {"message": "API is ready"}

@router.get("/status", tags=["System"])
def get_status() -> Dict[str, Any]:
    """
    Get detailed status information about the API
    """
    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "version": settings.VERSION,
        "python_version": sys.version,
        "platform": platform.platform()
    }

@router.get("/health", tags=["System"])
def health_check() -> Dict[str, str]:
    """
    Health check endpoint for monitoring
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/version", tags=["System"])
def get_version() -> Dict[str, str]:
    """
    Get API version information
    """
    return {
        "version": settings.VERSION,
        "build_date": "2024-03-19"
    } 