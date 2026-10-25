from fastapi import APIRouter
from app.config import settings
from app.schemas.skills import SkillsResponse

router = APIRouter(prefix="/api/skills", tags=["Skills"])


@router.get("", response_model=SkillsResponse)
def get_supported_skills() -> SkillsResponse:
    """Return the predefined list of supported skills for assessment."""
    return SkillsResponse(skills=settings.SUPPORTED_SKILLS)
