"""Sarvam AI Saaras v4 Speech-to-Text (STT) Service.

Uses Sarvam AI's official speech-to-text transcribe API (saaras:v4)
for highly accurate and reliable speech transcription.
"""

import asyncio
import io
import logging
import os
import time
import wave
from typing import AsyncGenerator, Dict, Optional, Tuple

import requests

try:
    from sarvamai import SarvamAI
except ImportError:
    SarvamAI = None  # Resilient fallback to direct requests REST API

from app.config import settings

logger = logging.getLogger("sarvam_stt")



def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """Pack raw linear PCM bytes (e.g. 16kHz 16-bit Int16 LE) into standard WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sampwidth)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return buf.getvalue()


class SarvamSTTAdapter:
    """Sarvam AI Saaras v4 STT Adapter.

    Supports:
    1. Transcribing audio files / blobs (WAV, WebM, MP3, etc.)
    2. Transcribing raw 16kHz PCM audio buffers
    3. Streaming STT via WebSocket with interim partial and final transcripts
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key
        self._client: Optional[SarvamAI] = None

    @property
    def provider_name(self) -> str:
        return "sarvam"

    def get_api_key(self) -> Optional[str]:
        key = self._api_key or settings.SARVAM_API_KEY or os.getenv("SARVAM_API_KEY")
        return key.strip() if key else None

    def is_configured(self) -> bool:
        key = self.get_api_key()
        return bool(key)

    def get_client(self) -> Optional[object]:
        if SarvamAI is None:
            return None
        api_key = self.get_api_key()
        if not api_key:
            raise RuntimeError(
                "Sarvam AI API key not configured. "
                "Set SARVAM_API_KEY in backend/.env to transcribe audio."
            )
        if self._client is None:
            self._client = SarvamAI(api_subscription_key=api_key)
        return self._client

    def transcribe_audio_bytes(
        self,
        audio_bytes: bytes,
        filename: str = "audio.wav",
        language_code: str = "unknown",
        mime_type: str = "audio/wav",
        model: str = "saaras:v4",
        mode: str = "codemix",
    ) -> Dict[str, object]:
        """Transcribe an audio buffer using Sarvam AI Saaras v4.
        
        Transcribes directly in the original spoken language (e.g. Tamil, Hindi,
        Bengali, Telugu) without translating to English.
        When language_code is 'unknown' or 'auto', Sarvam auto-detects
        the spoken language and transcribes the speech in that same language.
        """
        api_key = self.get_api_key()
        if not api_key:
            raise RuntimeError("Sarvam AI API key is not configured in backend/.env")

        start_time = time.time()
        transcript = ""
        used_sdk = False

        # Strictly enforce spoken language transcription without translation to English
        effective_mode = mode
        if effective_mode == "translate" or not effective_mode:
            logger.info("Enforcing original spoken language transcription: overriding translate -> codemix")
            effective_mode = "codemix"

        # Normalize auto/default/unknown to 'unknown' for Sarvam auto language detection
        target_lang = "unknown" if (not language_code or language_code.lower() in ("unknown", "auto", "default")) else language_code
        detected_language = target_lang

        if mime_type and ";" in mime_type:
            mime_type = mime_type.split(";")[0].strip()

        # First attempt: Official sarvamai SDK if available
        if SarvamAI is not None:
            try:
                client = self.get_client()
                if client:
                    response = client.speech_to_text.transcribe(
                        file=(filename, audio_bytes, mime_type),
                        model=model,
                        language_code=target_lang,
                        mode=effective_mode,
                    )
                    transcript = getattr(response, "transcript", "") or ""
                    detected_language = getattr(response, "language_code", None) or target_lang
                    used_sdk = True
                    logger.info(
                        "Sarvam SDK transcribe success: model=%s lang=%s detected=%s mode=%s transcript=%r (%.2f ms)",
                        model, target_lang, detected_language, effective_mode, transcript, (time.time() - start_time) * 1000
                    )
            except Exception as sdk_err:
                logger.warning("Sarvam SDK transcribe failed, attempting direct REST fallback: %s", sdk_err)

        if not used_sdk:
            # Direct REST fallback to https://api.sarvam.ai/speech-to-text
            try:
                headers = {"api-subscription-key": api_key}
                files = {"file": (filename, audio_bytes, mime_type)}
                data = {
                    "model": model,
                    "language_code": target_lang,
                    "mode": effective_mode,
                }
                res = requests.post(
                    "https://api.sarvam.ai/speech-to-text",
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=30,
                )
                if res.status_code == 200:
                    payload = res.json()
                    transcript = payload.get("transcript", "")
                    detected_language = payload.get("language_code", target_lang)
                    logger.info("Sarvam REST transcribe fallback success: %r (detected=%s)", transcript, detected_language)
                else:
                    logger.error("Sarvam REST error %d: %s", res.status_code, res.text)
                    raise RuntimeError(f"Sarvam API returned HTTP {res.status_code}: {res.text}")
            except Exception as rest_err:
                logger.error("Sarvam REST transcribe error: %s", rest_err)
                raise RuntimeError(f"Sarvam AI transcribe failure: {rest_err}") from rest_err

        latency_ms = round((time.time() - start_time) * 1000, 2)
        return {
            "transcript": transcript.strip(),
            "language_code": detected_language,
            "detected_language": detected_language,
            "latency_ms": latency_ms,
            "model": model,
        }

    def transcribe_pcm(
        self,
        pcm_bytes: bytes,
        sample_rate: int = 16000,
        language_code: str = "unknown",
        model: str = "saaras:v4",
    ) -> Dict[str, object]:
        """Convert linear 16-bit PCM bytes to WAV and transcribe with Sarvam."""
        if not pcm_bytes:
            return {"transcript": "", "latency_ms": 0, "language_code": language_code}
        wav_bytes = pcm_to_wav_bytes(pcm_data=pcm_bytes, sample_rate=sample_rate)
        return self.transcribe_audio_bytes(
            audio_bytes=wav_bytes,
            filename="stream.wav",
            language_code=language_code,
            mime_type="audio/wav",
            model=model,
        )

    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language_code: str = "unknown",
    ) -> AsyncGenerator[Dict[str, object], None]:
        """Process incoming 16kHz Int16 LE PCM stream from client WebSocket.

        Yields:
        - {"provider": "sarvam", "is_final": False, "transcript": "...", "latency_ms": ...} during speech
        - {"provider": "sarvam", "is_final": True, "transcript": "...", "latency_ms": ...} on finish
        """
        accumulated_chunks: list[bytes] = []
        out_queue: asyncio.Queue = asyncio.Queue()
        stream_active = True

        async def audio_collector():
            nonlocal stream_active
            try:
                async for chunk in audio_stream:
                    if chunk:
                        accumulated_chunks.append(chunk)
            finally:
                stream_active = False

        latest_partial_text = ""

        async def partial_transcriber():
            """Periodically transcribe accumulated speech for live preview feedback."""
            nonlocal latest_partial_text
            last_processed_bytes = 0
            while stream_active:
                await asyncio.sleep(0.8)
                current_bytes = sum(len(c) for c in accumulated_chunks)
                # Require at least 0.75 second (24000 bytes @ 16kHz 16-bit) and at least 0.35s of new audio
                if current_bytes >= 24000 and (current_bytes - last_processed_bytes) >= 12000:
                    last_processed_bytes = current_bytes
                    snap = b"".join(accumulated_chunks)
                    # Sarvam allows max 30s; keep snapshot within 25s (800,000 bytes)
                    snap_to_send = snap[-800000:] if len(snap) > 800000 else snap
                    try:
                        res = await asyncio.to_thread(
                            self.transcribe_pcm,
                            snap_to_send,
                            16000,
                            language_code,
                        )
                        partial_text = str(res.get("transcript", "")).strip()
                        if partial_text:
                            latest_partial_text = partial_text
                            logger.info("Sarvam partial preview: %r", partial_text)
                            await out_queue.put({
                                "provider": "sarvam",
                                "is_final": False,
                                "transcript": partial_text,
                                "latency_ms": res.get("latency_ms", 0),
                            })
                    except Exception as err:
                        logger.debug("Partial transcription notice: %s", err)

        async def pipeline_worker():
            try:
                collector_task = asyncio.create_task(audio_collector())
                partial_task = asyncio.create_task(partial_transcriber())

                # Wait for audio stream to conclude
                await collector_task
                partial_task.cancel()
                try:
                    await partial_task
                except asyncio.CancelledError:
                    pass

                # Perform final transcription of the complete audio
                all_pcm = b"".join(accumulated_chunks)
                total_duration_sec = len(all_pcm) / (16000 * 2)
                logger.info(
                    "Finalizing STT: collected %d bytes (%.2f seconds of audio)",
                    len(all_pcm), total_duration_sec
                )

                final_transcript = ""
                latency_ms = 0.0
                detected_lang = language_code

                if len(all_pcm) >= 8000:  # At least 0.25 seconds of audio
                    try:
                        # Sarvam 30s limit: chunk into 25s segments (800,000 bytes) if needed
                        max_chunk_bytes = 800000
                        if len(all_pcm) <= max_chunk_bytes:
                            res = await asyncio.to_thread(
                                self.transcribe_pcm,
                                all_pcm,
                                16000,
                                language_code,
                            )
                            final_transcript = str(res.get("transcript", "")).strip()
                            latency_ms = float(res.get("latency_ms", 0.0))
                            detected_lang = res.get("language_code") or res.get("detected_language") or language_code
                        else:
                            # Split into <=25s chunks and transcribe each
                            transcripts = []
                            for offset in range(0, len(all_pcm), max_chunk_bytes):
                                pcm_chunk = all_pcm[offset:offset + max_chunk_bytes]
                                if len(pcm_chunk) >= 8000:
                                    res = await asyncio.to_thread(
                                        self.transcribe_pcm,
                                        pcm_chunk,
                                        16000,
                                        language_code,
                                    )
                                    chunk_text = str(res.get("transcript", "")).strip()
                                    if chunk_text:
                                        transcripts.append(chunk_text)
                                    latency_ms += float(res.get("latency_ms", 0.0))
                                    if not detected_lang or detected_lang == "unknown":
                                        detected_lang = res.get("language_code") or res.get("detected_language") or detected_lang
                            final_transcript = " ".join(transcripts).strip()

                        if not final_transcript and latest_partial_text:
                            final_transcript = latest_partial_text

                        logger.info("Sarvam FINAL transcript: %r (lang=%s, latency=%.1f ms)", final_transcript, detected_lang, latency_ms)
                    except Exception as err:
                        logger.error("Final Sarvam transcription error: %s", err)
                        final_transcript = latest_partial_text
                else:
                    logger.info("Audio duration too short for transcription (%.2f s)", total_duration_sec)
                    final_transcript = latest_partial_text

                await out_queue.put({
                    "provider": "sarvam",
                    "is_final": True,
                    "transcript": final_transcript,
                    "language_code": detected_lang,
                    "latency_ms": latency_ms,
                })
            except Exception as pipeline_err:
                logger.error("STT pipeline worker error: %s", pipeline_err)
                await out_queue.put({
                    "provider": "sarvam",
                    "is_final": True,
                    "transcript": latest_partial_text,
                    "language_code": language_code,
                    "latency_ms": 0.0,
                    "error": str(pipeline_err),
                })
            finally:
                await out_queue.put(None)

        # Start background worker and yield events from queue in real time
        worker_task = asyncio.create_task(pipeline_worker())

        try:
            while True:
                item = await out_queue.get()
                if item is None:
                    break
                yield item
        finally:
            if not worker_task.done():
                worker_task.cancel()

