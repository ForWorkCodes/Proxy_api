from fastapi import APIRouter
from datetime import datetime
from typing import Dict, Any

router = APIRouter()

@router.post("/echo", tags=["Debug"])
def echo(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Echo endpoint for testing and debugging
    Returns the same data that was sent
    """
    return {
        "received_at": datetime.now().isoformat(),
        "data": data
    } 