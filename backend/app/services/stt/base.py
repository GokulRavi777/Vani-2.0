"""Speech-to-Text (STT) Provider Interface & Adapters.

Defines the contract and implementations for:
1. Google Cloud Speech-to-Text streaming linear16 transcription.
2. Sarvam AI Saaras v4 real-time WebSocket transcription.
3. Compare mode orchestrating dual streaming evaluation.
"""

from abc import ABC, abstractmethod
import asyncio
import json
import logging
import os
import time
from typing import AsyncGenerator, Dict, List, Optional

from app.config import settings
from app.schemas.assessment import STTMode

logger = logging.getLogger("stt_service")


class STTProviderInterface(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the STT provider (e.g., 'google', 'sarvam')."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if provider credentials/keys are configured."""
        pass

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language_code: str = "en-IN",
        keywords: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, object], None]:
        """Stream transcription results (interim and final)."""
        pass


class GoogleSTTAdapter(STTProviderInterface):
    """Google Cloud Speech-to-Text Streaming Adapter."""

    @property
    def provider_name(self) -> str:
        return "google"

    def is_configured(self) -> bool:
        cred_path = settings.GOOGLE_APPLICATION_CREDENTIALS or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.exists(cred_path):
            return True
        # Check if environment default credentials exist
        return bool(os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language_code: str = "en-IN",
        keywords: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, object], None]:
        if not self.is_configured():
            raise RuntimeError(
                "Google Cloud STT credentials not configured. "
                "Set GOOGLE_APPLICATION_CREDENTIALS in backend environment."
            )

        try:
            from google.cloud import speech
        except ImportError as e:
            raise RuntimeError("google-cloud-speech package not available.") from e

        client = speech.SpeechAsyncClient()
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code=language_code,
            enable_automatic_punctuation=True
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config,
            interim_results=True
        )

        async def request_generator():
            # First request contains config only
            yield speech.StreamingRecognizeRequest(streaming_config=streaming_config)
            async for chunk in audio_stream:
                if chunk:
                    yield speech.StreamingRecognizeRequest(audio_content=chunk)

        start_time = time.time()
        try:
            responses = await client.streaming_recognize(requests=request_generator())
            async for response in responses:
                for result in response.results:
                    if not result.alternatives:
                        continue
                    transcript = result.alternatives[0].transcript
                    latency_ms = round((time.time() - start_time) * 1000, 2)
                    yield {
                        "provider": "google",
                        "is_final": bool(result.is_final),
                        "transcript": transcript,
                        "confidence": getattr(result.alternatives[0], "confidence", 1.0),
                        "latency_ms": latency_ms
                    }
        except Exception as exc:
            logger.error("Google STT streaming error: %s", str(exc))
            raise RuntimeError(f"Google STT streaming failed: {str(exc)}") from exc


class SarvamSTTAdapter(STTProviderInterface):
    """Sarvam AI Saaras v4 Realtime Streaming Adapter."""

    @property
    def provider_name(self) -> str:
        return "sarvam"

    def is_configured(self) -> bool:
        key = settings.SARVAM_API_KEY or os.getenv("SARVAM_API_KEY")
        return bool(key and key.strip())

    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language_code: str = "en-IN",
        keywords: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, object], None]:
        api_key = settings.SARVAM_API_KEY or os.getenv("SARVAM_API_KEY")
        if not api_key:
            raise RuntimeError(
                "Sarvam AI API key not configured. "
                "Set SARVAM_API_KEY in backend environment."
            )

        import websockets

        url = f"wss://api.sarvam.ai/speech-to-text-realtime/ws?language_code={language_code}&model=saaras:v4"
        headers = {"api-subscription-key": api_key.strip()}

        start_time = time.time()
        try:
            async with websockets.connect(url, extra_headers=headers) as sarvam_ws:
                async def audio_feeder():
                    try:
                        async for chunk in audio_stream:
                            if chunk:
                                await sarvam_ws.send(chunk)
                    except Exception as feeder_err:
                        logger.debug("Sarvam feeder ended: %s", feeder_err)

                feeder_task = asyncio.create_task(audio_feeder())

                try:
                    async for message in sarvam_ws:
                        latency_ms = round((time.time() - start_time) * 1000, 2)
                        if isinstance(message, str):
                            try:
                                data = json.loads(message)
                                transcript = data.get("transcript") or data.get("text") or ""
                                msg_type = data.get("type", "")
                                is_final = msg_type in ("final", "done", "done_stt") or data.get("is_final", False)
                                yield {
                                    "provider": "sarvam",
                                    "is_final": is_final,
                                    "transcript": transcript,
                                    "latency_ms": latency_ms,
                                    "raw": data
                                }
                            except json.JSONDecodeError:
                                yield {
                                    "provider": "sarvam",
                                    "is_final": False,
                                    "transcript": message,
                                    "latency_ms": latency_ms
                                }
                finally:
                    feeder_task.cancel()
        except Exception as exc:
            logger.error("Sarvam STT streaming error: %s", str(exc))
            raise RuntimeError(f"Sarvam Saaras v4 STT failed: {str(exc)}") from exc


class STTBenchmarkOrchestrator:
    """Manages provider selection and dual comparative evaluation."""

    def __init__(self, mode: STTMode = "google"):
        self.mode = mode
        self.google_adapter = GoogleSTTAdapter()
        self.sarvam_adapter = SarvamSTTAdapter()

    def get_active_providers(self) -> List[STTProviderInterface]:
        if self.mode == "google":
            return [self.google_adapter]
        elif self.mode == "sarvam":
            return [self.sarvam_adapter]
        elif self.mode == "compare":
            return [self.google_adapter, self.sarvam_adapter]
        raise ValueError(f"Unknown STT mode: {self.mode}")
