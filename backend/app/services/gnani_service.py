"""Gnani AI Speech Service integration using the official pipecat-gnani plugin.

Provides:
1. GnaniStreamingSTTAdapter (using GnaniSTTService) for real-time WebSocket speech recognition.
2. GnaniHttpSTTAdapter (using GnaniHttpSTTService) for audio file blob REST transcription.
3. synthesize_speech (using GnaniHttpTTSService) for question synthesis with replay support.
4. Official verified voice catalog confirmed by Gnani documentation.
"""

import asyncio
import inspect
import io
import json
import logging
import os
import time
import wave
from typing import Any, Callable, Dict, List, Optional, Union

import aiohttp
import websockets
try:
    from pipecat.frames.frames import (
        ErrorFrame,
        Frame,
        InterimTranscriptionFrame,
        TranscriptionFrame,
        TTSAudioRawFrame,
    )
    from pipecat.transcriptions.language import Language
    from pipecat_gnani.stt import GnaniHttpSTTService, GnaniSTTService
    from pipecat_gnani.tts import GnaniHttpTTSService
except ImportError:
    Frame = object
    ErrorFrame = object
    InterimTranscriptionFrame = object
    TranscriptionFrame = object
    TTSAudioRawFrame = object
    class Language:
        EN_IN = "en-IN"
        HI_IN = "hi-IN"
        TA_IN = "ta-IN"
        TE_IN = "te-IN"
        KN_IN = "kn-IN"
        ML_IN = "ml-IN"
        BN_IN = "bn-IN"
        GU_IN = "gu-IN"
        MR_IN = "mr-IN"
        PA_IN = "pa-IN"
    GnaniHttpSTTService = object
    GnaniHttpTTSService = object
    GnaniSTTService = object

from app.config import settings

logger = logging.getLogger("gnani_service")

# Official verified voices catalog from Gnani documentation (Timbre v2.5 / Pipecat plugin)
# Reference: https://docs.gnani.ai/api/TTS/available-voices.md
SUPPORTED_GNANI_VOICES: List[Dict[str, str]] = [
    {
        "id": "Pranav",
        "name": "Pranav (Male)",
        "language": "en-IN",
        "language_name": "English (India)",
        "gender": "Male",
        "persona": "Friendly",
        "description": "Friendly voice for customer support & assessments (Default)"
    },
    {
        "id": "Kaveri",
        "name": "Kaveri (Female)",
        "language": "en-IN",
        "language_name": "English (India)",
        "gender": "Female",
        "persona": "Professional",
        "description": "Firm, polished voice for technical assessment"
    },
    {
        "id": "Devika",
        "name": "Devika (Female)",
        "language": "en-IN",
        "language_name": "English (India)",
        "gender": "Female",
        "persona": "Professional",
        "description": "Authoritative professional voice"
    },
    {
        "id": "Shlok",
        "name": "Shlok (Male)",
        "language": "en-IN",
        "language_name": "English (India)",
        "gender": "Male",
        "persona": "Conversational",
        "description": "Warm, conversational interview voice"
    },
    {
        "id": "Girish",
        "name": "Girish (Male)",
        "language": "en-IN",
        "language_name": "English (India)",
        "gender": "Male",
        "persona": "Expressive",
        "description": "Warm voice with natural cadence"
    },
    {
        "id": "Trupti",
        "name": "Trupti (Female)",
        "language": "en-IN",
        "language_name": "English (India)",
        "gender": "Female",
        "persona": "Professional",
        "description": "Upbeat, articulate voice with maturity"
    },
    {
        "id": "Nalini",
        "name": "Nalini (Female)",
        "language": "hi-IN",
        "language_name": "Hindi",
        "gender": "Female",
        "persona": "Friendly",
        "description": "Friendly conversational Hindi voice"
    },
    {
        "id": "Deepak",
        "name": "Deepak (Male)",
        "language": "hi-IN",
        "language_name": "Hindi",
        "gender": "Male",
        "persona": "Professional",
        "description": "Clear, measured voice for corporate use"
    },
    {
        "id": "Poorvi",
        "name": "Poorvi (Female)",
        "language": "hi-en",
        "language_name": "Hinglish",
        "gender": "Female",
        "persona": "Conversational",
        "description": "Natural voice for bilingual English/Hindi questions"
    },
    {
        "id": "Asmita",
        "name": "Asmita (Female)",
        "language": "ta-IN",
        "language_name": "Tamil",
        "gender": "Female",
        "persona": "Professional",
        "description": "Polished corporate voice in Tamil"
    },
    {
        "id": "Suhana",
        "name": "Suhana (Female)",
        "language": "te-IN",
        "language_name": "Telugu",
        "gender": "Female",
        "persona": "Warm",
        "description": "Calm, soothing voice in Telugu"
    },
    {
        "id": "Saanvi",
        "name": "Saanvi (Female)",
        "language": "kn-IN",
        "language_name": "Kannada",
        "gender": "Female",
        "persona": "Expressive",
        "description": "Lively, expressive Kannada voice"
    },
    {
        "id": "Reshma",
        "name": "Reshma (Female)",
        "language": "ml-IN",
        "language_name": "Malayalam",
        "gender": "Female",
        "persona": "Friendly",
        "description": "Bright, clear Malayalam voice"
    },
    {
        "id": "Dhruva",
        "name": "Dhruva (Male)",
        "language": "bn-IN",
        "language_name": "Bengali",
        "gender": "Male",
        "persona": "Conversational",
        "description": "Casual, relatable voice in Bengali"
    },
    {
        "id": "Falak",
        "name": "Falak (Female)",
        "language": "gu-IN",
        "language_name": "Gujarati",
        "gender": "Female",
        "persona": "Conversational",
        "description": "Youthful, clear voice in Gujarati"
    },
    {
        "id": "Zahira",
        "name": "Zahira (Female)",
        "language": "mr-IN",
        "language_name": "Marathi",
        "gender": "Female",
        "persona": "Expressive",
        "description": "Energetic, expressive Marathi voice"
    },
    {
        "id": "Mehuli",
        "name": "Mehuli (Female)",
        "language": "pa-IN",
        "language_name": "Punjabi",
        "gender": "Female",
        "persona": "Expressive",
        "description": "Expressive Punjabi voice"
    }
]

# Language code to Pipecat Language enum mapping
LANGUAGE_MAP: Dict[str, Language] = {
    "en-IN": Language.EN_IN,
    "hi-IN": Language.HI_IN,
    "ta-IN": Language.TA_IN,
    "te-IN": Language.TE_IN,
    "kn-IN": Language.KN_IN,
    "ml-IN": Language.ML_IN,
    "bn-IN": Language.BN_IN,
    "gu-IN": Language.GU_IN,
    "mr-IN": Language.MR_IN,
    "pa-IN": Language.PA_IN,
}


def get_gnani_api_key() -> Optional[str]:
    key = settings.GNANI_API_KEY or os.getenv("GNANI_API_KEY")
    return key.strip() if key else None


def is_gnani_configured() -> bool:
    return bool(get_gnani_api_key())


def resolve_pipecat_language(lang_code: Optional[str]) -> Union[Language, str]:
    """Resolve language code for Gnani STT.
    
    When unknown, auto, or indic-auto is passed, returns 'indic-auto'
    for official Gnani automatic language identification and transcription in the spoken language.
    """
    if not lang_code or str(lang_code).strip().lower() in ("unknown", "auto", "default", "indic-auto"):
        return "indic-auto"
    code = str(lang_code).strip()
    return LANGUAGE_MAP.get(code, code)


def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """Wrap linear PCM bytes in standard WAV container."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sampwidth)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return buf.getvalue()


# Gnani Voice Activity Detection (VAD) Tuning Presets
# Reference: https://docs.gnani.ai/api/STT/stt-websocket#voice-activity-detection-vad-tuning
GNANI_VAD_PRESETS: Dict[str, Dict[str, Any]] = {
    "interview_optimal": {
        "id": "interview_optimal",
        "name": "Interview Optimal (Recommended)",
        "description": "Tuned specifically for technical interview answers. Tolerates thinking pauses without segment splitting, with rapid phrase delivery.",
        "vad_threshold": 0.55,
        "min_silence_ms": 700,
        "min_speech_ms": 120,
        "min_segment_ms": 120,
        "max_speech_s": 20.0,
    },
    "fast_turnaround": {
        "id": "fast_turnaround",
        "name": "Fast Turnaround / Rapid Fire",
        "description": "Lowest latency response (350ms silence window). Best for brief one-word or rapid short answers.",
        "vad_threshold": 0.60,
        "min_silence_ms": 350,
        "min_speech_ms": 100,
        "min_segment_ms": 100,
        "max_speech_s": 15.0,
    },
    "noisy_room": {
        "id": "noisy_room",
        "name": "Noisy Room / Laptop Mic",
        "description": "Higher confidence threshold (0.72) and extended speech gate (220ms) to filter out keyboard clatter and room chatter.",
        "vad_threshold": 0.72,
        "min_silence_ms": 600,
        "min_speech_ms": 220,
        "min_segment_ms": 220,
        "max_speech_s": 25.0,
    },
    "monologue_heavy": {
        "id": "monologue_heavy",
        "name": "Long Monologue / Deep Explanation",
        "description": "Extended pause tolerance (900ms) with a 30s forced segment cap to ensure steady transcript flow during long explanations.",
        "vad_threshold": 0.50,
        "min_silence_ms": 900,
        "min_speech_ms": 150,
        "min_segment_ms": 150,
        "max_speech_s": 30.0,
    },
}


def build_gnani_vad_headers(
    api_key: str,
    language_code: str = "indic-auto",
    preset: Optional[str] = "interview_optimal",
    vad_threshold: Optional[float] = None,
    min_silence_ms: Optional[int] = None,
    min_speech_ms: Optional[int] = None,
    min_segment_ms: Optional[int] = None,
    max_speech_s: Optional[float] = None,
    sample_rate: int = 16000,
    enable_word_boosting: bool = True
) -> Dict[str, str]:
    """Construct official Gnani WebSocket upgrade headers with full VAD tuning parameters."""
    preset_data = GNANI_VAD_PRESETS.get(preset or "interview_optimal", GNANI_VAD_PRESETS["interview_optimal"])

    thresh = vad_threshold if vad_threshold is not None else preset_data["vad_threshold"]
    silence = min_silence_ms if min_silence_ms is not None else preset_data["min_silence_ms"]
    speech = min_speech_ms if min_speech_ms is not None else preset_data["min_speech_ms"]
    segment = min_segment_ms if min_segment_ms is not None else preset_data["min_segment_ms"]
    max_speech = max_speech_s if max_speech_s is not None else preset_data.get("max_speech_s", 20.0)

    # Clamp according to documented limits
    thresh_clamped = max(0.0, min(1.0, float(thresh)))
    silence_clamped = max(100, min(2000, int(silence)))
    speech_clamped = max(50, min(2000, int(speech)))
    segment_clamped = max(100, min(1000, int(segment)))

    resolved_lang = "en-IN" if not language_code or language_code.lower() in ("unknown", "auto", "default", "indic-auto") else language_code

    headers = {
        "x-api-key-id": api_key,
        "lang_code": resolved_lang,
        "x-sample-rate": str(sample_rate),
        "x-format": "transcribe",
        "x-vad-threshold": f"{thresh_clamped:.2f}",
        "x-min-silence-ms": str(silence_clamped),
        "x-min-speech-ms": str(speech_clamped),
        "x-min-segment-ms": str(segment_clamped),
        "x-partials": "true",
        "x-partial-interval-ms": "250",
    }

    if max_speech is not None and float(max_speech) >= 5.0:
        max_s_clamped = min(120.0, float(max_speech))
        headers["x-max-speech-s"] = f"{max_s_clamped:.1f}"

    if enable_word_boosting:
        headers["x-bias-list"] = json.dumps(["Python", "SQL", "Java", "tuple", "mutable", "immutable", "indexing", "algorithm"])
        headers["x-bias-score"] = "1.5"

    return headers


class GnaniRealtimeSTTClient:
    """Raw WebSocket client for Gnani AI Speech-to-Text v3 stream.

    Fully implements the 5 Voice Activity Detection (VAD) parameters,
    streaming 1,024-byte PCM frames (512 samples at 16kHz) as required by
    https://docs.gnani.ai/api/STT/stt-websocket#voice-activity-detection-vad-tuning
    """

    def __init__(
        self,
        api_key: str,
        language_code: str = "en-IN",
        on_transcript: Optional[Callable[[Dict[str, Any]], Any]] = None,
        preset: str = "interview_optimal",
        vad_threshold: Optional[float] = None,
        min_silence_ms: Optional[int] = None,
        min_speech_ms: Optional[int] = None,
        min_segment_ms: Optional[int] = None,
        max_speech_s: Optional[float] = None,
        sample_rate: int = 16000
    ):
        self.api_key = api_key
        self.language_code = language_code
        self.on_transcript = on_transcript
        self.sample_rate = sample_rate
        self.headers = build_gnani_vad_headers(
            api_key=api_key,
            language_code=language_code,
            preset=preset,
            vad_threshold=vad_threshold,
            min_silence_ms=min_silence_ms,
            min_speech_ms=min_speech_ms,
            min_segment_ms=min_segment_ms,
            max_speech_s=max_speech_s,
            sample_rate=sample_rate
        )
        self.ws = None
        self._audio_queue: asyncio.Queue = asyncio.Queue()
        self._receive_task: Optional[asyncio.Task] = None
        self._send_task: Optional[asyncio.Task] = None
        self._closed = False
        self._buffer = bytearray()
        self.active_config: Dict[str, Any] = {}

    async def start(self):
        url = getattr(settings, "GNANI_STT_WS_ENDPOINT", "wss://api.vachana.ai/stt/v3/stream")
        connect_kwargs = {}
        if "extra_headers" in inspect.signature(websockets.connect).parameters:
            connect_kwargs["extra_headers"] = self.headers
        else:
            connect_kwargs["additional_headers"] = self.headers

        logger.info(
            "Connecting to Gnani STT WebSocket (lang=%s, threshold=%s, silence=%sms, speech_gate=%sms, max_speech=%ss, partials=true)",
            self.headers.get("lang_code"),
            self.headers.get("x-vad-threshold"),
            self.headers.get("x-min-silence-ms"),
            self.headers.get("x-min-speech-ms"),
            self.headers.get("x-max-speech-s", "none")
        )

        self.ws = await websockets.connect(url, **connect_kwargs)
        self._send_task = asyncio.create_task(self._send_loop())
        self._receive_task = asyncio.create_task(self._receive_loop())

    async def send_audio_chunk(self, chunk: bytes):
        if self._closed or not chunk:
            return
        self._buffer.extend(chunk)
        # Flush in exact 1,024-byte chunks (512 samples * 2 bytes at 16kHz)
        while len(self._buffer) >= 1024:
            frame = bytes(self._buffer[:1024])
            del self._buffer[:1024]
            await self._audio_queue.put(frame)

    @property
    def is_ws_open(self) -> bool:
        if not self.ws:
            return False
        # websockets >= 14 uses State enum on self.ws.state
        state = getattr(self.ws, "state", None)
        if state is not None:
            return getattr(state, "name", "") == "OPEN" or getattr(state, "value", None) == 1
        # legacy websockets used ws.closed boolean or ws.open
        if hasattr(self.ws, "open"):
            return bool(self.ws.open)
        return not getattr(self.ws, "closed", True)

    async def _send_loop(self):
        try:
            while not self._closed:
                item = await self._audio_queue.get()
                if item is None:
                    break
                if self.is_ws_open:
                    await self.ws.send(item)
        except Exception as e:
            logger.debug("Gnani send_loop stopped: %s", e)

    async def _receive_loop(self):
        try:
            while not self._closed and self.is_ws_open:
                msg = await self.ws.recv()
                if not msg:
                    continue
                try:
                    data = json.loads(msg)
                except Exception:
                    continue

                msg_type = data.get("type")
                if msg_type == "connected":
                    self.active_config = data.get("config", {})
                    logger.info("Gnani VAD connection confirmed: %s", self.active_config)
                elif msg_type in ("speech_start", "processing"):
                    if self.on_transcript:
                        await self.on_transcript({
                            "is_processing": True,
                            "raw": data
                        })
                elif msg_type in ("partial_transcript", "partial", "interim"):
                    text = (data.get("text") or data.get("transcript") or "").strip()
                    if text and self.on_transcript:
                        await self.on_transcript({
                            "transcript": text,
                            "is_final": False,
                            "is_partial": True,
                            "latency_ms": data.get("latency", 0),
                            "segment_id": data.get("segment_id"),
                            "raw": data
                        })
                elif msg_type in ("final_transcript", "transcript", "final"):
                    text = (data.get("text") or data.get("transcript") or "").strip()
                    if text and self.on_transcript:
                        await self.on_transcript({
                            "transcript": text,
                            "is_final": True,
                            "is_partial": False,
                            "latency_ms": data.get("latency", 0),
                            "segment_id": data.get("segment_id"),
                            "audio_duration_ms": data.get("audio_duration_ms", 0),
                            "raw": data
                        })
                elif msg_type == "error":
                    err_msg = data.get("message") or "Unknown Gnani STT error"
                    logger.error("Gnani STT error received: %s", err_msg)
                    if self.on_transcript:
                        await self.on_transcript({"is_error": True, "error": err_msg})
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            logger.debug("Gnani receive_loop stopped: %s", e)

    async def close(self):
        if self._closed:
            return
        self._closed = True

        if len(self._buffer) > 0:
            pad_len = 1024 - len(self._buffer)
            self._buffer.extend(b"\x00" * pad_len)
            await self._audio_queue.put(bytes(self._buffer))
            self._buffer.clear()

        await self._audio_queue.put(None)
        if self._send_task:
            try:
                await asyncio.wait_for(self._send_task, timeout=1.0)
            except Exception:
                self._send_task.cancel()

        # Wait briefly for server to return final transcripts
        await asyncio.sleep(0.5)

        if self._receive_task:
            self._receive_task.cancel()

        if self.is_ws_open:
            try:
                await self.ws.close()
            except Exception:
                pass


class GnaniStreamingSTTAdapter(GnaniSTTService):
    """GnaniSTTService adapter for real-time WebSocket speech recognition.
    
    Intercepts downstream transcription frames from Gnani's WebSocket
    and invokes a callback to deliver them to the client WebSocket session.
    Supports 'indic-auto' for auto-detecting Indian languages and
    transcribing in the spoken language.
    """

    def __init__(
        self,
        api_key: str,
        language: Union[Language, str] = "indic-auto",
        on_transcript: Optional[Callable[[Dict[str, Any]], Any]] = None,
        sample_rate: int = 16000,
        format: str = "transcribe"
    ):
        settings_obj = GnaniSTTService.Settings(
            language=language,
            sample_rate=sample_rate,
            format=format
        )
        super().__init__(api_key=api_key, settings=settings_obj)
        self._on_transcript = on_transcript
        self._language = language

    async def push_frame(self, frame: Frame, direction: Any = None):
        """Intercept frame emissions from Pipecat STTService."""
        if isinstance(frame, (TranscriptionFrame, InterimTranscriptionFrame)):
            is_final = getattr(frame, "is_final", True)
            text = getattr(frame, "text", "")
            if text and self._on_transcript:
                await self._on_transcript({
                    "is_final": is_final,
                    "transcript": text
                })
        elif isinstance(frame, ErrorFrame):
            logger.error("Gnani STT error frame: %s", frame.error)
            if self._on_transcript:
                await self._on_transcript({
                    "is_error": True,
                    "error": frame.error
                })


async def synthesize_question_speech(
    text: str,
    voice: Optional[str] = None,
    language_code: str = "en-IN",
    sample_rate: int = 16000
) -> bytes:
    """Synthesize question text into audio bytes using official GnaniHttpTTSService.

    Returns:
        WAV audio bytes.
    """
    api_key = get_gnani_api_key()
    if not api_key:
        raise RuntimeError("Gnani API key (GNANI_API_KEY) is not configured in backend/.env")

    selected_voice = voice or settings.GNANI_DEFAULT_VOICE or "Pranav"
    model = settings.GNANI_TTS_MODEL or "timbre-v2.5"

    tts_settings = GnaniHttpTTSService.Settings(
        voice=selected_voice,
        model=model,
        encoding="linear_pcm",
        container="wav",
        sample_width=2
    )

    async with aiohttp.ClientSession() as session:
        tts_service = GnaniHttpTTSService(
            api_key=api_key,
            aiohttp_session=session,
            model=model,
            sample_rate=sample_rate,
            settings=tts_settings
        )

        audio_chunks: List[bytes] = []
        async for frame in tts_service.run_tts(text, context_id="q_tts"):
            if isinstance(frame, TTSAudioRawFrame):
                audio_chunks.append(frame.audio)
            elif isinstance(frame, ErrorFrame):
                raise RuntimeError(f"Gnani TTS synthesis failed: {frame.error}")

    if not audio_chunks:
        raise RuntimeError("Gnani TTS returned no audio frames.")

    pcm_data = b"".join(audio_chunks)
    # If the response already contains a WAV header, return it directly; otherwise pack into WAV.
    if len(pcm_data) >= 12 and pcm_data[:4] == b"RIFF" and pcm_data[8:12] == b"WAVE":
        return pcm_data
    return pcm_to_wav_bytes(pcm_data, sample_rate=sample_rate)


async def synthesize_cloned_voice_speech(
    text: str,
    speaker_embedding: Dict[str, Any],
    sample_rate: int = 16000
) -> bytes:
    """Synthesize text into WAV audio using Gnani AI Voice Cloning model (vachana-vc-v1).

    Args:
        text: Text prompt to synthesize.
        speaker_embedding: Verified speaker embedding tensor dictionary.
        sample_rate: Desired audio sample rate (default: 16000).

    Returns:
        bytes: Binary WAV audio data.
    """
    api_key = get_gnani_api_key()
    if not api_key:
        raise RuntimeError("Gnani API key (GNANI_API_KEY) is not configured in backend/.env")

    tts_payload = {
        "text": text.strip(),
        "model": "vachana-vc-v1",
        "speaker_embedding": speaker_embedding,
        "audio_config": {
            "sample_rate": sample_rate,
            "encoding": "linear_pcm",
            "container": "wav",
            "num_channels": 1,
            "sample_width": 2
        }
    }

    url = settings.GNANI_TTS_ENDPOINT or "https://api.vachana.ai/api/v1/tts/inference"
    headers = {
        "X-API-Key-ID": api_key,
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=tts_payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                err_text = await resp.text()
                logger.error("Gnani Cloned Voice TTS error (HTTP %d): %s", resp.status, err_text)
                raise RuntimeError(f"Gnani Cloned Voice TTS failed (HTTP {resp.status}): {err_text}")
            audio_bytes = await resp.read()

    if not audio_bytes:
        raise RuntimeError("Gnani Cloned Voice TTS returned empty audio.")

    if len(audio_bytes) >= 12 and audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        return audio_bytes
    return pcm_to_wav_bytes(audio_bytes, sample_rate=sample_rate)


async def transcribe_audio_file_gnani(
    audio_bytes: bytes,
    language_code: str = "indic-auto",
    sample_rate: int = 16000,
    format: str = "transcribe"
) -> Dict[str, Any]:
    """Transcribe complete audio bytes using official GnaniHttpSTTService.

    When language_code is 'indic-auto' (or 'unknown'/'auto'), Gnani auto-detects
    the language and transcribes the speech into that same language.

    Returns:
        Dict with transcript, latency_ms, provider, model, language_code.
    """
    api_key = get_gnani_api_key()
    if not api_key:
        raise RuntimeError("Gnani API key (GNANI_API_KEY) is not configured in backend/.env")

    resolved_lang = resolve_pipecat_language(language_code)
    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        stt_service = GnaniHttpSTTService(
            api_key=api_key,
            aiohttp_session=session,
            sample_rate=sample_rate,
            settings=GnaniHttpSTTService.Settings(
                language=resolved_lang,
                format=format
            )
        )

        transcript = ""
        async for frame in stt_service.run_stt(audio_bytes):
            if isinstance(frame, TranscriptionFrame):
                transcript = frame.text
            elif isinstance(frame, ErrorFrame):
                raise RuntimeError(f"Gnani HTTP STT failed: {frame.error}")

    latency_ms = round((time.time() - start_time) * 1000, 2)
    lang_str = str(resolved_lang) if isinstance(resolved_lang, str) else getattr(resolved_lang, "value", "indic-auto")
    return {
        "transcript": transcript.strip(),
        "latency_ms": latency_ms,
        "provider": "gnani",
        "model": "gnani-prisma-v2.5",
        "language_code": lang_str
    }
