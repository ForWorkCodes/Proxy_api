from app.core.app import create_app
from fastapi import FastAPI, HTTPException
from datetime import datetime
from typing import Dict, Any
import platform
import sys

app = create_app()

@app.get("/")
def root():
    return {"message": "API is ready"}

@app.get("/status", tags=["System"])
def get_status() -> Dict[str, Any]:
    """
    Get detailed status information about the API
    """
    return {
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "python_version": sys.version,
        "platform": platform.platform()
    }

@app.get("/health", tags=["System"])
def health_check() -> Dict[str, str]:
    """
    Health check endpoint for monitoring
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/version", tags=["System"])
def get_version() -> Dict[str, str]:
    """
    Get API version information
    """
    return {
        "version": "1.0.0",
        "build_date": "2024-03-19"
    }

@app.post("/echo", tags=["Debug"])
def echo(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Echo endpoint for testing and debugging
    Returns the same data that was sent
    """
    return {
        "received_at": datetime.now().isoformat(),
        "data": data
    }
