"""TTS Router for question audio synthesis and voice catalogue."""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, status, UploadFile
from pydantic import BaseModel, Field

from app.config import settings
from app.services.session_store import SessionStoreInterface, get_session_store
from app.services.tts.gnani_adapter import GnaniTTSAdapter, GnaniTTSError
from app.services.tts.sarvam_adapter import SarvamTTSAdapter, SarvamTTSError, SUPPORTED_SARVAM_VOICES

logger = logging.getLogger("tts_router")

router = APIRouter(prefix="/api/tts", tags=["Text-to-Speech"])

# In-memory audio cache for synthesized questions: {f"{provider}:{question_id}:{voice}": bytes}
_audio_cache: Dict[str, bytes] = {}


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Question or prompt text to read aloud")
    voice: Optional[str] = Field(default=None, description="Voice ID from supported catalogue")
    language: Optional[str] = Field(default="en-IN", description="Language code")
    provider: Optional[str] = Field(default="sarvam", description="TTS provider (sarvam or gnani)")


@router.get("/voices", summary="Get supported TTS voices for configured provider")
def get_voices(
    provider: str = Query("sarvam", description="TTS provider name (sarvam or gnani)"),
    language: Optional[str] = Query(None, description="Filter voices by language code")
):
    """Retrieve supported voices catalogue for the configured TTS model."""
    prov = provider.lower()
    if prov == "gnani":
        voices = GnaniTTSAdapter.get_supported_voices(language=language)
        return {
            "provider": "gnani",
            "model": settings.GNANI_TTS_MODEL,
            "default_voice": settings.GNANI_DEFAULT_VOICE or "Kaveri",
            "count": len(voices),
            "voices": voices
        }
    elif prov == "sarvam":
        voices = SarvamTTSAdapter.get_supported_voices(language=language)
        return {
            "provider": "sarvam",
            "model": "bulbul:v3",
            "default_voice": "shubh",
            "count": len(voices),
            "voices": voices
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"TTS provider '{provider}' is not supported for voice listing."
        )


@router.post("/synthesize", summary="Synthesize speech audio from text")
async def synthesize_text(request: SynthesizeRequest):
    """Synthesize text into WAV audio using the requested provider and voice."""
    prov = (request.provider or "sarvam").lower()

    if prov == "sarvam":
        adapter = SarvamTTSAdapter()
        if not adapter.is_configured():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sarvam API key (SARVAM_API_KEY) is not configured in backend/.env"
            )
        try:
            audio_bytes = await adapter.synthesize(
                text=request.text,
                language_code=request.language or "en-IN",
                voice_name=request.voice or "shubh"
            )
        except SarvamTTSError as err:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err))

    elif prov == "gnani":
        adapter = GnaniTTSAdapter()
        if not adapter.is_configured():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gnani API key (GNANI_API_KEY) is not configured in backend/.env"
            )
        try:
            audio_bytes = await adapter.synthesize(
                text=request.text,
                language_code=request.language or "en-IN",
                voice_name=request.voice or "Kaveri"
            )
        except GnaniTTSError as err:
            err_msg = str(err)
            if "Unsupported voice" in err_msg:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=err_msg)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"TTS provider '{request.provider}' is not supported."
        )

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": "inline; filename=question_audio.wav"}
    )


@router.get(
    "/assessments/{assessment_id}/questions/{question_id}",
    summary="Get or synthesize audio for a specific assessment question"
)
async def get_question_audio(
    assessment_id: str,
    question_id: str,
    voice: Optional[str] = Query(None, description="Voice override; defaults to session voice"),
    provider: Optional[str] = Query(None, description="TTS provider override; defaults to session provider"),
    session_store: SessionStoreInterface = Depends(get_session_store)
):
    """Retrieve question audio for an active assessment session.

    Uses session-persisted provider and voice, and caches synthesized audio in memory.
    """
    session = session_store.get(assessment_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment '{assessment_id}' not found."
        )

    # Locate question in session
    target_q = None
    for q in session.questions:
        if q.question_id == question_id:
            target_q = q
            break

    if not target_q:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question '{question_id}' not found in assessment '{assessment_id}'."
        )

    effective_provider = (provider or session.provider or "sarvam").lower()

    # Resolve voice: query param -> session voice -> default voice for provider
    if effective_provider == "sarvam":
        selected_voice = voice or session.voice or "shubh"
    else:
        selected_voice = voice or session.voice or settings.GNANI_DEFAULT_VOICE or "Kaveri"

    cache_key = f"{effective_provider}:{question_id}:{selected_voice}"

    if cache_key in _audio_cache:
        logger.info("Serving cached question audio for key %s", cache_key)
        return Response(
            content=_audio_cache[cache_key],
            media_type="audio/wav",
            headers={"Content-Disposition": f"inline; filename={question_id}.wav"}
        )

    if effective_provider == "sarvam":
        s_adapter = SarvamTTSAdapter()
        if not s_adapter.is_configured():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sarvam API key (SARVAM_API_KEY) is not configured in backend/.env"
            )
        try:
            audio_bytes = await s_adapter.synthesize(
                text=target_q.text,
                language_code=session.language or "en-IN",
                voice_name=selected_voice
            )
        except SarvamTTSError as err:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(err))

    else:
        g_adapter = GnaniTTSAdapter()
        if not g_adapter.is_configured():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gnani API key (GNANI_API_KEY) is not configured in backend/.env"
            )
        try:
            audio_bytes = await g_adapter.synthesize(
                text=target_q.text,
                language_code=session.language or "en-IN",
                voice_name=selected_voice
            )
        except GnaniTTSError as err:
            err_msg = str(err)
            if "Unsupported voice" in err_msg:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=err_msg)

    # Cache for replays and navigation
    _audio_cache[cache_key] = audio_bytes

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": f"inline; filename={question_id}.wav"}
    )


@router.post("/voice-clone/enroll", status_code=status.HTTP_201_CREATED, summary="Enroll a custom voice for interview questions")
async def enroll_voice(
    file: UploadFile = File(..., description="Audio recording of user voice (WAV, MP3, etc., 5-30 seconds)"),
    voice_name: str = Form("My Voice", description="Human-readable voice name"),
    consent: bool = Form(..., description="Explicit user consent acknowledging ownership of voice"),
    language: str = Form("en-IN", description="Target language code")
):
    """Secure backend-only voice cloning enrollment workflow using Gnani AI."""
    from app.services.voice_cloning_service import enroll_custom_voice, VoiceEnrollmentError

    if not consent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit user consent is strictly required to clone and enroll your voice."
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio recording is empty."
        )

    filename = file.filename or "recording.wav"

    try:
        enrolled = enroll_custom_voice(
            audio_bytes=content,
            filename=filename,
            voice_name=voice_name,
            consent_verified=consent,
            language=language
        )
        return {
            "success": True,
            "message": "Voice enrolled successfully",
            "voice": enrolled
        }
    except VoiceEnrollmentError as err:
        err_msg = str(err)
        logger.error("Voice enrollment failure: %s", err_msg)
        if "authorization failed" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=err_msg)
        if "not configured" in err_msg.lower():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)
    except Exception as exc:
        logger.error("Unexpected voice enrollment error: %s", exc)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.get("/voice-clone/voices", summary="List enrolled custom voices")
def list_enrolled_voices():
    """Retrieve all enrolled custom voices."""
    from app.services.custom_voice_store import get_custom_voice_store
    store = get_custom_voice_store()
    voices = store.list_voices()
    return {
        "count": len(voices),
        "voices": voices
    }


@router.delete("/voice-clone/voices/{voice_id}", summary="Delete an enrolled custom voice")
def delete_enrolled_voice(voice_id: str):
    """Delete an enrolled custom voice by ID."""
    from app.services.custom_voice_store import get_custom_voice_store
    store = get_custom_voice_store()
    deleted = store.delete_voice(voice_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Custom voice '{voice_id}' not found."
        )
    return {"success": True, "message": f"Voice '{voice_id}' deleted."}
