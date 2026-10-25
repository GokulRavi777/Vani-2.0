from typing import List
from pydantic import BaseModel, Field


class SkillsResponse(BaseModel):
    skills: List[str] = Field(
        ...,
        description="List of supported technical skills available for assessment"
    )
