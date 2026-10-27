"""Gnani AI Text-to-Speech (TTS) Adapter.

Implements TTSProviderInterface for synthesizing interview questions into audio.
Uses Gnani AI's Vachana TTS inference service via official pipecat-gnani plugin.
"""

import logging
from typing import Dict, List, Optional

from app.config import settings
from app.services.tts.base import TTSProviderInterface
from app.services import gnani_service
from app.services.custom_voice_store import get_custom_voice_store

logger = logging.getLogger("gnani_tts_adapter")


class GnaniTTSError(Exception):
    """Exception raised when Gnani TTS synthesis fails or configuration is invalid."""
    pass


class GnaniTTSAdapter(TTSProviderInterface):
    """Provider-neutral adapter for Gnani AI Text-to-Speech synthesis."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self._api_key = api_key
        self.model = model or getattr(settings, "GNANI_TTS_MODEL", "timbre-v2.5")

    def get_api_key(self) -> Optional[str]:
        if self._api_key:
            return self._api_key
        return gnani_service.get_gnani_api_key()

    def is_configured(self) -> bool:
        return bool(self.get_api_key())

    @classmethod
    def get_supported_voices(cls, language: Optional[str] = None) -> List[Dict[str, str]]:
        """Return list of supported Gnani voices, including enrolled custom voices."""
        voices: List[Dict[str, str]] = []

        # 1. Include verified custom cloned voices at the top
        try:
            custom_store = get_custom_voice_store()
            custom_voices = custom_store.list_voices()
            for cv in custom_voices:
                voices.append({
                    "id": cv["id"],
                    "name": f"🎙️ {cv['name']} (My Cloned Voice)",
                    "language": cv.get("language", "en-IN"),
                    "gender": cv.get("gender", "Custom"),
                    "persona": "Cloned Voice",
                    "description": cv.get("description", "Custom voice cloned via Gnani AI"),
                    "is_custom": True
                })
        except Exception as e:
            logger.warning("Could not load custom voices: %s", e)

        # 2. Append standard verified Gnani catalogue voices
        voices.extend(gnani_service.SUPPORTED_GNANI_VOICES)

        if not language:
            return voices

        lang_lower = language.lower()
        return [
            v for v in voices
            if v["language"].lower() == lang_lower or (lang_lower == "en" and v["language"].startswith("en"))
        ]

    async def synthesize(
        self,
        text: str,
        language_code: str = "en-IN",
        voice_name: Optional[str] = None
    ) -> bytes:
        """Synthesize question text into WAV audio bytes using Gnani AI.

        When voice_name is an enrolled custom voice ID, uses Gnani Voice Cloning
        model (vachana-vc-v1) with the verified speaker embedding.
        If a custom voice fails or is unavailable, falls back to standard voice.

        Args:
            text: Text of the question to synthesize.
            language_code: Target BCP-47 language (default: 'en-IN').
            voice_name: Supported voice identifier or custom voice ID.

        Returns:
            bytes: Binary WAV audio data.

        Raises:
            GnaniTTSError: When credentials are missing, voice is unsupported, or API returns error.
        """
        api_key = self.get_api_key()
        if not api_key:
            raise GnaniTTSError("Gnani API key (GNANI_API_KEY) is not configured in backend/.env")

        if not text or not text.strip():
            raise GnaniTTSError("Text to synthesize cannot be empty.")

        voice = voice_name or getattr(settings, "GNANI_DEFAULT_VOICE", "Pranav")

        # Check if the requested voice is an enrolled custom cloned voice
        custom_store = get_custom_voice_store()
        custom_voice_record = custom_store.get_voice(voice) if custom_store else None

        if custom_voice_record and "speaker_embedding" in custom_voice_record:
            logger.info("Synthesizing question with enrolled custom voice '%s' (%s)", custom_voice_record["name"], voice)
            try:
                audio_bytes = await gnani_service.synthesize_cloned_voice_speech(
                    text=text.strip(),
                    speaker_embedding=custom_voice_record["speaker_embedding"]
                )
                return audio_bytes
            except Exception as clone_err:
                logger.warning(
                    "Custom voice synthesis failed (%s), attempting fallback to default voice: %s",
                    voice, clone_err
                )
                # Fallback to standard voice
                voice = getattr(settings, "GNANI_DEFAULT_VOICE", "Pranav")

        # Standard Gnani voice validation
        valid_standard_voice_ids = [v["id"] for v in gnani_service.SUPPORTED_GNANI_VOICES]
        all_valid_voice_ids = valid_standard_voice_ids + [cv["id"] for cv in custom_store.list_voices()]

        if voice not in all_valid_voice_ids and voice not in valid_standard_voice_ids:
            raise GnaniTTSError(
                f"Unsupported voice '{voice}'. Supported voices: {', '.join(valid_standard_voice_ids[:6])}..."
            )

        try:
            audio_bytes = await gnani_service.synthesize_question_speech(
                text=text.strip(),
                voice=voice,
                language_code=language_code
            )
            return audio_bytes
        except Exception as exc:
            err_msg = str(exc)
            logger.error("Gnani TTS synthesis failed: %s", err_msg)
            if "SCOPE_NOT_ALLOWED" in err_msg or "Service 'TTS' not in allowed scopes" in err_msg:
                raise GnaniTTSError(
                    "Service 'TTS' not in allowed scopes for this Gnani API key. "
                    "Please enable the 'TTS' service scope for your API key in the Gnani.ai dashboard."
                )
            raise GnaniTTSError(f"Gnani TTS synthesis failed: {err_msg}")
