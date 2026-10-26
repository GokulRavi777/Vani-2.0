from app.routers.health import router as health_router
from app.routers.skills import router as skills_router
from app.routers.assessments import router as assessments_router
from app.routers.stt import router as stt_router

__all__ = ["health_router", "skills_router", "assessments_router", "stt_router"]
