from fastapi import APIRouter, Depends, HTTPException, status
import uuid

from app.schemas.assessment import (
    CreateAssessmentRequest,
    AssessmentResponse
)
from app.services.session_store import SessionStoreInterface, get_session_store
from app.services.question_generator import (
    QuestionGeneratorInterface,
    QuestionGenerationError,
    get_question_generator
)

router = APIRouter(prefix="/api/assessments", tags=["Assessments"])


@router.post(
    "",
    response_model=AssessmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new assessment session and generate questions"
)
def create_assessment(
    request: CreateAssessmentRequest,
    session_store: SessionStoreInterface = Depends(get_session_store),
    generator: QuestionGeneratorInterface = Depends(get_question_generator)
) -> AssessmentResponse:
    """Validate selected skills, generate exactly two relevant questions,

    and initialize an in-memory assessment session.
    """
    try:
        questions, mode = generator.generate(
            skills=request.skills,
            question_count=request.question_count,
            allow_fallback=True
        )
    except QuestionGenerationError as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Question generation failed: {str(err)}"
        )

    assessment_id = f"asm_{uuid.uuid4().hex[:12]}"

    assessment = AssessmentResponse(
        assessment_id=assessment_id,
        skills=request.skills,
        language=request.language,
        question_generation_mode=mode,
        stt_mode=request.stt_mode or "google",
        questions=questions
    )

    session_store.save(assessment)
    return assessment


@router.get(
    "/{assessment_id}",
    response_model=AssessmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve an existing assessment session"
)
def get_assessment(
    assessment_id: str,
    session_store: SessionStoreInterface = Depends(get_session_store)
) -> AssessmentResponse:
    """Retrieve an assessment by ID. Does NOT regenerate questions on read."""
    session = session_store.get(assessment_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{assessment_id}' not found."
        )
    return session
