from fastapi import APIRouter
from typing import Dict

router = APIRouter(tags=["Health"])


@router.get("/health")
def get_health() -> Dict[str, str]:
    """Health check endpoint confirming service status."""
    return {
        "status": "healthy",
        "service": "vani-2.0-poc",
        "stage": "1"
    }
