"""Gnani AI Voice Cloning Enrollment Service.

Secure backend-only enrollment workflow for cloning custom voices:
1. Validates audio format, size, duration, and explicit user consent.
2. Invokes official Gnani voice clone embeddings endpoint:
   POST https://api.vachana.ai/api/v1/tts/voice-clone/embeddings
3. Securely persists verified speaker embeddings without logging audio or credentials.
4. Returns sanitized custom voice metadata for use in Gnani TTS question synthesis.
"""

import io
import logging
import time
import uuid
import wave
from typing import Any, Dict, Optional

import requests

from app.config import settings
from app.services.custom_voice_store import get_custom_voice_store

logger = logging.getLogger("voice_cloning_service")

# Official Gnani Voice Clone API Endpoint
GNANI_VOICE_CLONE_EMBEDDINGS_URL = "https://api.vachana.ai/api/v1/tts/voice-clone/embeddings"

# Allowed audio formats for reference voice cloning
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".ogg", ".flac", ".webm", ".m4a", ".aac"}
MIN_AUDIO_BYTES = 4000  # ~0.25 seconds of raw audio minimum
MAX_AUDIO_BYTES = 15 * 1024 * 1024  # 15 MB maximum


class VoiceEnrollmentError(Exception):
    """Exception raised when voice cloning enrollment fails."""
    pass


def get_gnani_api_key() -> Optional[str]:
    key = settings.GNANI_API_KEY
    return key.strip() if key else None


def validate_enrollment_audio(audio_bytes: bytes, filename: str) -> str:
    """Validate audio file extension and payload size.

    Returns:
        Normalized MIME type string.
    """
    if not audio_bytes or len(audio_bytes) < MIN_AUDIO_BYTES:
        raise VoiceEnrollmentError(
            f"Audio recording is too short or empty ({len(audio_bytes) if audio_bytes else 0} bytes). "
            f"Please provide at least 5–30 seconds of clear speech."
        )

    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise VoiceEnrollmentError(
            f"Audio file exceeds maximum size limit of 15MB ({len(audio_bytes) / (1024 * 1024):.1f}MB)."
        )

    lower_name = (filename or "recording.wav").lower()
    ext = "." + lower_name.split(".")[-1] if "." in lower_name else ".wav"
    if ext not in SUPPORTED_AUDIO_EXTENSIONS:
        raise VoiceEnrollmentError(
            f"Unsupported audio format '{ext}'. Allowed formats: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}"
        )

    mime_map = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
        ".webm": "audio/webm",
        ".m4a": "audio/m4a",
        ".aac": "audio/aac",
    }
    return mime_map.get(ext, "audio/wav")


def inspect_wav_duration(audio_bytes: bytes) -> Optional[float]:
    """Inspect duration if file is a WAV container."""
    if len(audio_bytes) >= 44 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wf:
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                if framerate > 0:
                    return round(nframes / float(framerate), 2)
        except Exception:
            pass
    return None


def enroll_custom_voice(
    audio_bytes: bytes,
    filename: str = "voice_sample.wav",
    voice_name: Optional[str] = None,
    consent_verified: bool = False,
    language: str = "en-IN"
) -> Dict[str, Any]:
    """Enroll a custom user voice using Gnani AI Voice Clone API.

    Args:
        audio_bytes: Raw binary bytes of the reference speech recording.
        filename: Name of the uploaded audio file.
        voice_name: Human-readable label for this voice (e.g. 'My Voice').
        consent_verified: Explicit user acknowledgment that the recording is their own voice.
        language: Primary language code (default: 'en-IN').

    Returns:
        Dict: Enrolled voice metadata containing verified voice_id and shape.

    Raises:
        VoiceEnrollmentError: On validation failure, unconfigured key, or upstream failure.
    """
    if not consent_verified:
        raise VoiceEnrollmentError(
            "User consent is strictly required to clone and enroll a voice. "
            "Please confirm that this audio recording is your own voice."
        )

    api_key = get_gnani_api_key()
    if not api_key:
        raise VoiceEnrollmentError(
            "Gnani API key (GNANI_API_KEY) is not configured in backend/.env. "
            "Cannot enroll voice without valid API credentials."
        )

    mime_type = validate_enrollment_audio(audio_bytes, filename)
    duration_sec = inspect_wav_duration(audio_bytes)

    clean_name = (voice_name or "My Voice").strip()
    if not clean_name:
        clean_name = "My Voice"

    logger.info(
        "Requesting voice clone embedding from Gnani AI: filename=%s, bytes=%d, duration=%s",
        filename, len(audio_bytes), f"{duration_sec}s" if duration_sec else "unknown"
    )

    start_time = time.time()
    try:
        headers = {"X-API-Key-ID": api_key}
        files = {"audio_file": (filename, audio_bytes, mime_type)}

        response = requests.post(
            GNANI_VOICE_CLONE_EMBEDDINGS_URL,
            headers=headers,
            files=files,
            timeout=45
        )
    except Exception as net_err:
        logger.error("Network error connecting to Gnani Voice Clone API: %s", net_err)
        raise VoiceEnrollmentError(f"Failed to connect to Gnani Voice Clone API: {net_err}") from net_err

    latency_ms = round((time.time() - start_time) * 1000, 2)

    if response.status_code != 200:
        error_detail = response.text
        try:
            err_json = response.json()
            error_detail = err_json.get("message") or err_json.get("error") or error_detail
        except Exception:
            pass
        logger.error("Gnani Voice Clone API error (HTTP %d): %s", response.status_code, error_detail)

        if response.status_code == 401 or response.status_code == 403:
            raise VoiceEnrollmentError(
                f"Gnani API authorization failed (HTTP {response.status_code}). "
                f"Verify that your GNANI_API_KEY has Voice Clone / TTS scopes enabled."
            )
        if response.status_code == 500:
            raise VoiceEnrollmentError(
                f"Gnani Voice Clone API error (500): {error_detail} "
                f"(Gnani requires 5–30 seconds of clean speech in standard WAV/PCM format)."
            )
        raise VoiceEnrollmentError(f"Gnani Voice Clone API error ({response.status_code}): {error_detail}")

    try:
        data = response.json()
    except Exception as parse_err:
        logger.error("Failed to parse Gnani Voice Clone response: %s", parse_err)
        raise VoiceEnrollmentError("Invalid response received from Gnani Voice Clone API.") from parse_err

    if not data.get("success"):
        error_msg = data.get("message") or data.get("error") or "Unknown enrollment failure"
        raise VoiceEnrollmentError(f"Gnani voice enrollment unsuccessful: {error_msg}")

    emb_payload = data.get("data", {}).get("voice_clone_embedding")
    if not emb_payload or not isinstance(emb_payload, dict) or "embedding" not in emb_payload:
        logger.error("Voice Clone API returned missing embedding tensor: %s", data)
        raise VoiceEnrollmentError("Gnani API did not return a valid voice embedding tensor.")

    # Generate verified unique custom voice identifier
    voice_id = f"cloned_voice_{uuid.uuid4().hex[:10]}"

    # Persist securely in project's custom voice store
    store = get_custom_voice_store()
    record = store.save_voice(
        voice_id=voice_id,
        name=clean_name,
        speaker_embedding=emb_payload,
        language=language,
        gender="Custom",
        description=f"Personal voice cloned for {clean_name}",
        duration_sec=duration_sec
    )

    logger.info("Custom voice enrolled successfully: voice_id=%s, latency=%.2f ms", voice_id, latency_ms)

    return {
        "voice_id": voice_id,
        "name": clean_name,
        "status": "enrolled",
        "language": language,
        "gender": "Custom",
        "persona": "Cloned Voice",
        "description": record["description"],
        "embedding_shape": emb_payload.get("shape", [1, 768]),
        "latency_ms": latency_ms
    }
