from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator
from app.config import settings

STTMode = Literal["google", "sarvam", "gnani", "compare"]
QuestionGenerationMode = Literal["ai", "fallback"]


class QuestionModel(BaseModel):
    question_id: str = Field(..., description="Unique identifier for the question")
    text: str = Field(..., min_length=10, description="The interview question text")
    skills: List[str] = Field(..., min_length=1, description="Skills targeted by this question")


class CreateAssessmentRequest(BaseModel):
    skills: List[str] = Field(
        ...,
        min_length=1,
        description="Candidate selected skills (at least one required)"
    )
    language: str = Field(
        default=settings.DEFAULT_LANGUAGE,
        description="Interview language code, e.g. en-IN"
    )
    question_count: int = Field(
        default=2,
        description="Number of questions to generate. Prototype strictly enforces 2."
    )
    stt_mode: Optional[STTMode] = Field(
        default=settings.DEFAULT_STT_MODE,
        description="Provider-neutral configuration for STT mode"
    )
    provider: Optional[str] = Field(
        default="sarvam",
        description="Selected AI provider (sarvam or gnani)"
    )
    voice: Optional[str] = Field(
        default=None,
        description="Selected voice identifier for interviewer TTS reading"
    )

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("At least one skill must be selected.")
        
        # Deduplicate while preserving order
        unique_skills = []
        for s in v:
            s_clean = s.strip()
            if s_clean and s_clean not in unique_skills:
                unique_skills.append(s_clean)
                
        if not unique_skills:
            raise ValueError("At least one non-empty skill must be selected.")

        unsupported = [s for s in unique_skills if s not in settings.SUPPORTED_SKILLS]
        if unsupported:
            raise ValueError(
                f"Unsupported skills: {', '.join(unsupported)}. "
                f"Supported skills are: {', '.join(settings.SUPPORTED_SKILLS)}"
            )
        return unique_skills

    @field_validator("question_count")
    @classmethod
    def validate_question_count(cls, v: int) -> int:
        if v != 2:
            raise ValueError("Stage 1 prototype strictly requires exactly 2 questions.")
        return v


class AnswerModel(BaseModel):
    question_id: str = Field(..., description="The ID of the question being answered")
    transcript: str = Field(default="", description="The text transcript of the candidate's answer")
    audio_metadata: Optional[dict] = Field(default=None, description="Metadata about the recorded audio")
    latency_ms: Optional[float] = Field(default=None, description="STT latency in milliseconds")
    provider: Optional[str] = Field(default=None, description="STT provider used")
    comparison_results: Optional[dict] = Field(default=None, description="Dual provider comparison results if applicable")
    submitted_at: Optional[str] = Field(default=None, description="ISO timestamp of answer submission")


class SubmitAnswerRequest(BaseModel):
    question_id: str = Field(..., description="The ID of the question being answered")
    transcript: Optional[str] = Field(default="", description="The text transcript of the candidate's answer")
    audio_metadata: Optional[dict] = Field(default=None, description="Metadata about the recorded audio")
    latency_ms: Optional[float] = Field(default=None, description="STT latency in milliseconds")
    provider: Optional[str] = Field(default=None, description="STT provider used")
    comparison_results: Optional[dict] = Field(default=None, description="Dual provider comparison results if applicable")


class AssessmentResponse(BaseModel):
    assessment_id: str = Field(..., description="Unique assessment session identifier")
    skills: List[str] = Field(..., description="Selected skills for this assessment")
    language: str = Field(..., description="Assessment language")
    question_generation_mode: QuestionGenerationMode = Field(
        ...,
        description="Origin of questions: 'ai' (configured generator) or 'fallback' (deterministic bank)"
    )
    stt_mode: Optional[STTMode] = Field(
        default=settings.DEFAULT_STT_MODE,
        description="STT provider mode configuration"
    )
    provider: Optional[str] = Field(
        default="sarvam",
        description="Active provider for this assessment (sarvam or gnani)"
    )
    voice: Optional[str] = Field(
        default=None,
        description="Configured interviewer voice for TTS playback"
    )
    questions: List[QuestionModel] = Field(
        ...,
        min_length=2,
        max_length=2,
        description="List of exactly 2 generated questions"
    )
    answers: Optional[dict] = Field(
        default_factory=dict,
        description="Candidate submitted answers keyed by question_id"
    )
