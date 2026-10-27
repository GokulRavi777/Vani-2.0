"""Sarvam AI Text-to-Speech (TTS) Adapter.

Implements TTSProviderInterface for synthesizing interview questions into audio
using Sarvam AI's official Bulbul TTS model.
"""

import asyncio
import base64
import logging
import os
from typing import Dict, List, Optional
import requests

from app.config import settings
from app.services.tts.base import TTSProviderInterface

logger = logging.getLogger("sarvam_tts_adapter")

SUPPORTED_SARVAM_VOICES: List[Dict[str, str]] = [
    {
        "id": "shubh",
        "name": "Shubh (Male)",
        "language": "en-IN",
        "gender": "Male",
        "persona": "Professional",
        "description": "Clear, professional, and articulate male interviewer voice"
    },
    {
        "id": "ritu",
        "name": "Ritu (Female)",
        "language": "en-IN",
        "gender": "Female",
        "persona": "Crisp",
        "description": "Crisp, friendly, and natural female interviewer voice"
    },
    {
        "id": "aditya",
        "name": "Aditya (Male)",
        "language": "en-IN",
        "gender": "Male",
        "persona": "Confident",
        "description": "Confident and warm male voice"
    },
    {
        "id": "priya",
        "name": "Priya (Female)",
        "language": "en-IN",
        "gender": "Female",
        "persona": "Warm",
        "description": "Warm, polite, and engaging female voice"
    },
    {
        "id": "neha",
        "name": "Neha (Female)",
        "language": "en-IN",
        "gender": "Female",
        "persona": "Expressive",
        "description": "Expressive, bright female voice"
    },
    {
        "id": "rahul",
        "name": "Rahul (Male)",
        "language": "en-IN",
        "gender": "Male",
        "persona": "Conversational",
        "description": "Casual, conversational male voice"
    },
    {
        "id": "pooja",
        "name": "Pooja (Female)",
        "language": "en-IN",
        "gender": "Female",
        "persona": "Gentle",
        "description": "Gentle, calm female voice"
    },
    {
        "id": "rohan",
        "name": "Rohan (Male)",
        "language": "en-IN",
        "gender": "Male",
        "persona": "Authoritative",
        "description": "Authoritative technical lead voice"
    },
    {
        "id": "simran",
        "name": "Simran (Female)",
        "language": "en-IN",
        "gender": "Female",
        "persona": "Energetic",
        "description": "Energetic and positive female voice"
    },
    {
        "id": "kavya",
        "name": "Kavya (Female)",
        "language": "en-IN",
        "gender": "Female",
        "persona": "Fluent",
        "description": "Fluent, articulate female voice"
    }
]


class SarvamTTSError(Exception):
    """Exception raised when Sarvam TTS synthesis fails."""
    pass


class SarvamTTSAdapter(TTSProviderInterface):
    """Provider adapter for Sarvam AI Bulbul Text-to-Speech synthesis."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key

    def get_api_key(self) -> Optional[str]:
        return (self._api_key or settings.SARVAM_API_KEY or os.getenv("SARVAM_API_KEY") or "").strip() or None

    def is_configured(self) -> bool:
        return bool(self.get_api_key())

    @classmethod
    def get_supported_voices(cls, language: Optional[str] = None) -> List[Dict[str, str]]:
        if not language:
            return list(SUPPORTED_SARVAM_VOICES)
        lang_lower = language.lower()
        return [
            v for v in SUPPORTED_SARVAM_VOICES
            if v["language"].lower() == lang_lower or (lang_lower == "en" and v["language"].startswith("en"))
        ]

    async def synthesize(
        self,
        text: str,
        language_code: str = "en-IN",
        voice_name: Optional[str] = None
    ) -> bytes:
        api_key = self.get_api_key()
        if not api_key:
            raise SarvamTTSError("Sarvam API key (SARVAM_API_KEY) is not configured in backend/.env")

        speaker = (voice_name or "shubh").lower().strip()
        # Clean language code
        lang = "en-IN" if not language_code or language_code.lower() in ("unknown", "auto") else language_code

        def _call_sarvam():
            try:
                from sarvamai import SarvamAI
                client = SarvamAI(api_subscription_key=api_key)
                response = client.text_to_speech.convert(
                    text=text,
                    language_code=lang,
                    speaker=speaker,
                    model="bulbul:v3"
                )
                if response and hasattr(response, "audios") and response.audios:
                    return base64.b64decode(response.audios[0])
            except Exception as sdk_err:
                logger.warning("Sarvam SDK TTS error: %s. Falling back to REST API.", sdk_err)

            url = "https://api.sarvam.ai/text-to-speech"
            headers = {
                "api-subscription-key": api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "inputs": [text],
                "target_language_code": lang,
                "speaker": speaker,
                "model": "bulbul:v3"
            }
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if not resp.ok:
                raise SarvamTTSError(f"Sarvam TTS failed: HTTP {resp.status_code} - {resp.text}")
            data = resp.json()
            audios = data.get("audios") or []
            if not audios:
                raise SarvamTTSError("Sarvam TTS returned no audio data.")
            return base64.b64decode(audios[0])

        return await asyncio.to_thread(_call_sarvam)
