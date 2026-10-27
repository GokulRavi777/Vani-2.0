"""STT Router for Sarvam AI Saaras v4 transcription.

Supports:
1. Real-time WebSocket streaming with live partials and final transcript
2. REST audio upload endpoint (POST /api/stt/transcribe) for direct audio blobs
"""

import asyncio
import logging
import time
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, UploadFile, File, HTTPException

from app.config import settings
from app.services.stt.base import SarvamSTTAdapter
from app.services.gnani_service import (
    GnaniStreamingSTTAdapter,
    GnaniRealtimeSTTClient,
    GNANI_VAD_PRESETS,
    build_gnani_vad_headers,
    get_gnani_api_key,
    is_gnani_configured,
    resolve_pipecat_language,
    transcribe_audio_file_gnani,
)

logger = logging.getLogger("stt_router")

router = APIRouter(tags=["STT Streaming"])


async def handle_gnani_websocket_stt(
    websocket: WebSocket,
    language_code: str = "unknown",
    assessment_id: Optional[str] = None,
    question_id: Optional[str] = None,
    preset: str = "interview_optimal",
    vad_threshold: float = settings.GNANI_VAD_THRESHOLD,
    min_silence_ms: int = settings.GNANI_MIN_SILENCE_MS,
    min_speech_ms: int = settings.GNANI_MIN_SPEECH_MS,
    min_segment_ms: int = settings.GNANI_MIN_SEGMENT_MS,
    max_speech_s: float = settings.GNANI_MAX_SPEECH_S
):
    """Handle real-time candidate audio streaming with official Gnani VAD tuning."""
    if not is_gnani_configured():
        logger.error("Gnani API key not configured!")
        await websocket.send_json({
            "type": "error",
            "provider": "gnani",
            "question_id": question_id,
            "error": "Gnani AI API key (GNANI_API_KEY) is not configured in backend/.env."
        })
        await websocket.close()
        return

    api_key = get_gnani_api_key()
    lang_param = resolve_pipecat_language(language_code)
    lang_str = str(lang_param) if isinstance(lang_param, str) else getattr(lang_param, "value", "indic-auto")
    start_time = time.time()
    last_audio_chunk_time = time.time()
    chunk_count = 0
    accumulated_segments: list[str] = []
    last_partial_text: str = ""

    logger.info(
        "⚡ Initializing Gnani STT WebSocket session: preset=%s, threshold=%.2f, silence=%dms, speech=%dms, segment=%dms, max_speech=%.1fs",
        preset, vad_threshold, min_silence_ms, min_speech_ms, min_segment_ms, max_speech_s
    )

    async def on_gnani_transcript(evt: dict):
        nonlocal last_partial_text
        if evt.get("is_error"):
            await websocket.send_json({
                "type": "error",
                "provider": "gnani",
                "question_id": question_id,
                "error": evt.get("error", "Gnani STT error occurred")
            })
        elif evt.get("is_processing"):
            # VAD engine has confirmed human speech onset
            await websocket.send_json({
                "type": "processing",
                "provider": "gnani",
                "question_id": question_id,
                "message": "Speech detected by VAD engine",
                "latencyMs": round((time.time() - start_time) * 1000, 1)
            })
        else:
            text = (evt.get("transcript") or "").strip()
            if not text:
                return

            turnaround_ms = round((time.time() - last_audio_chunk_time) * 1000, 1)
            reported_latency = evt.get("latency_ms") or turnaround_ms

            if evt.get("is_partial") or not evt.get("is_final"):
                last_partial_text = text
                # Real-time interim partial update streamed while candidate is speaking
                current_display = (" ".join(accumulated_segments) + " " + text).strip() if accumulated_segments else text
                logger.info("🎙️ Gnani live partial stream: %r", current_display)

                await websocket.send_json({
                    "type": "partial",
                    "transcript": current_display,
                    "segment_text": text,
                    "is_partial": True,
                    "question_id": question_id,
                    "provider": "gnani",
                    "language_code": lang_str,
                    "latencyMs": reported_latency,
                    "turnaroundMs": turnaround_ms,
                    "segment_id": evt.get("segment_id")
                })
            else:
                # Segment finalized by VAD silence trigger
                last_partial_text = ""
                accumulated_segments.append(text)
                full_live_transcript = " ".join(accumulated_segments)

                logger.info(
                    "⚡ Gnani VAD segment finalized: %r (turnaround=%sms, silence_gate=%sms, lang=%s)",
                    text, turnaround_ms, min_silence_ms, lang_str
                )

                await websocket.send_json({
                    "type": "partial",
                    "transcript": full_live_transcript,
                    "segment_text": text,
                    "is_partial": False,
                    "question_id": question_id,
                    "provider": "gnani",
                    "language_code": lang_str,
                    "latencyMs": reported_latency,
                    "turnaroundMs": turnaround_ms,
                    "min_silence_ms": min_silence_ms,
                    "vad_threshold": vad_threshold,
                    "preset": preset,
                    "segment_id": evt.get("segment_id")
                })
                await websocket.send_json({
                    "type": "final",
                    "transcript": full_live_transcript,
                    "segment_text": text,
                    "is_partial": False,
                    "question_id": question_id,
                    "provider": "gnani",
                    "language_code": lang_str,
                    "latencyMs": reported_latency,
                    "turnaroundMs": turnaround_ms,
                    "min_silence_ms": min_silence_ms,
                    "vad_threshold": vad_threshold,
                    "preset": preset,
                    "segment_id": evt.get("segment_id")
                })

    realtime_client = GnaniRealtimeSTTClient(
        api_key=api_key,
        language_code=lang_str,
        on_transcript=on_gnani_transcript,
        preset=preset,
        vad_threshold=vad_threshold,
        min_silence_ms=min_silence_ms,
        min_speech_ms=min_speech_ms,
        min_segment_ms=min_segment_ms,
        max_speech_s=max_speech_s,
        sample_rate=16000
    )

    try:
        await realtime_client.start()
        await websocket.send_json({
            "type": "connected",
            "provider": "gnani",
            "message": "Connected to Gnani STT v3 with Voice Activity Detection (VAD)",
            "vad_headers": realtime_client.headers,
            "active_preset": preset,
            "vad_threshold": vad_threshold,
            "min_silence_ms": min_silence_ms,
            "min_speech_ms": min_speech_ms,
            "min_segment_ms": min_segment_ms,
            "max_speech_s": max_speech_s
        })
    except Exception as conn_err:
        logger.error("Failed to connect to Gnani STT WebSocket: %s", conn_err)
        await websocket.send_json({
            "type": "error",
            "provider": "gnani",
            "question_id": question_id,
            "error": f"Failed to connect to Gnani STT WebSocket: {conn_err}"
        })
        await websocket.close()
        return

    try:
        while True:
            message = await websocket.receive()
            msg_type = message.get("type", "")

            if msg_type == "websocket.disconnect":
                logger.info("Client disconnected from Gnani STT: question=%s, chunks=%d", question_id, chunk_count)
                break

            bytes_data = message.get("bytes")
            if bytes_data:
                chunk_count += 1
                last_audio_chunk_time = time.time()
                await realtime_client.send_audio_chunk(bytes_data)

            elif message.get("text"):
                text_cmd = message.get("text", "").strip()
                if text_cmd in ("stop", "end", "close"):
                    logger.info("Gnani stop command received for question=%s", question_id)
                    await realtime_client.close()
                    if last_partial_text and (not accumulated_segments or accumulated_segments[-1] != last_partial_text):
                        accumulated_segments.append(last_partial_text)
                    final_full = " ".join(accumulated_segments)
                    await websocket.send_json({
                        "type": "final",
                        "transcript": final_full,
                        "question_id": question_id,
                        "provider": "gnani",
                        "language_code": lang_str,
                        "latencyMs": round((time.time() - start_time) * 1000, 2)
                    })
                    break

    except WebSocketDisconnect:
        logger.info("Gnani WebSocket disconnected: question=%s, chunks=%d", question_id, chunk_count)
    except Exception as exc:
        logger.error("Gnani WebSocket receive error for question=%s: %s", question_id, exc)
    finally:
        await realtime_client.close()
        logger.info("Gnani STT session cleaned up for question=%s", question_id)


async def handle_websocket_stt(
    websocket: WebSocket,
    language_code: str = "unknown",
    assessment_id: Optional[str] = None,
    question_id: Optional[str] = None,
    provider: Optional[str] = "sarvam",
    preset: str = "interview_optimal",
    vad_threshold: float = settings.GNANI_VAD_THRESHOLD,
    min_silence_ms: int = settings.GNANI_MIN_SILENCE_MS,
    min_speech_ms: int = settings.GNANI_MIN_SPEECH_MS,
    min_segment_ms: int = settings.GNANI_MIN_SEGMENT_MS,
    max_speech_s: float = settings.GNANI_MAX_SPEECH_S
):
    await websocket.accept()
    logger.info(
        "WebSocket STT connected: lang=%s, assessment=%s, question=%s, provider=%s, preset=%s",
        language_code, assessment_id, question_id, provider, preset
    )

    if provider and provider.lower() == "gnani":
        await handle_gnani_websocket_stt(
            websocket=websocket,
            language_code=language_code,
            assessment_id=assessment_id,
            question_id=question_id,
            preset=preset,
            vad_threshold=vad_threshold,
            min_silence_ms=min_silence_ms,
            min_speech_ms=min_speech_ms,
            min_segment_ms=min_segment_ms,
            max_speech_s=max_speech_s
        )
        return

    adapter = SarvamSTTAdapter()

    if not adapter.is_configured():
        logger.error("Sarvam API key not configured!")
        await websocket.send_json({
            "type": "error",
            "provider": "sarvam",
            "question_id": question_id,
            "error": "Sarvam AI API key (SARVAM_API_KEY) is not configured in backend/.env."
        })
        await websocket.close()
        return

    # Normalize language for Sarvam auto-detection
    sarvam_target_lang = "unknown" if (not language_code or language_code.lower() in ("unknown", "auto", "default")) else language_code

    audio_queue: asyncio.Queue = asyncio.Queue()
    chunk_count = 0

    async def audio_stream_generator():
        """Yields audio chunks from queue. Stops on None sentinel."""
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                logger.info("Audio stream ended for question=%s (sentinel received)", question_id)
                break
            yield chunk

    async def transcription_worker():
        """Connects to Sarvam and streams transcription results back to frontend."""
        try:
            logger.info("Starting Sarvam transcription for question=%s (lang=%s)", question_id, sarvam_target_lang)
            event_count = 0
            async for event in adapter.transcribe_stream(
                audio_stream_generator(), language_code=sarvam_target_lang
            ):
                event_count += 1
                msg_type = "final" if event.get("is_final") else "partial"
                transcript = event.get("transcript", "")
                detected_lang = event.get("language_code") or sarvam_target_lang
                logger.info(
                    "Transcript event #%d type=%s text=%r lang=%s latency=%.0fms",
                    event_count, msg_type, transcript, detected_lang, event.get("latency_ms", 0)
                )
                try:
                    await websocket.send_json({
                        "type": msg_type,
                        "transcript": transcript,
                        "question_id": question_id,
                        "provider": "sarvam",
                        "language_code": detected_lang,
                        "latencyMs": event.get("latency_ms")
                    })
                except Exception as send_err:
                    logger.warning("Failed to send transcript to client: %s", send_err)
                    break

            logger.info("Transcription done for question=%s, events=%d", question_id, event_count)

        except Exception as err:
            logger.warning("Transcription worker error for question=%s: %s", question_id, str(err))
            try:
                await websocket.send_json({
                    "type": "error",
                    "provider": "sarvam",
                    "question_id": question_id,
                    "error": str(err)
                })
            except Exception:
                pass

    worker_task = asyncio.create_task(transcription_worker())

    try:
        while True:
            message = await websocket.receive()
            msg_type = message.get("type", "")

            if msg_type == "websocket.disconnect":
                logger.info("Client disconnected: question=%s, chunks_received=%d", question_id, chunk_count)
                break

            # Binary PCM audio chunk from AudioCaptureService (16kHz Int16 LE)
            bytes_data = message.get("bytes")
            if bytes_data:
                chunk_count += 1
                if chunk_count % 10 == 1:
                    logger.debug(
                        "Audio chunk #%d (%d bytes) for question=%s",
                        chunk_count, len(bytes_data), question_id
                    )
                await audio_queue.put(bytes_data)

            elif message.get("text"):
                text_cmd = message.get("text", "").strip()
                logger.info("Text command received: %r for question=%s", text_cmd, question_id)
                if text_cmd in ("stop", "end", "close"):
                    logger.info("Stop command — signalling end of audio stream")
                    await audio_queue.put(None)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for question=%s, chunks=%d", question_id, chunk_count)
    except Exception as exc:
        logger.error("WebSocket receive loop error for question=%s: %s", question_id, str(exc))
    finally:
        # Signal end of audio to Sarvam, then wait briefly for final transcripts
        await audio_queue.put(None)

        # Give Sarvam up to 6 seconds to return final transcripts before cancelling
        try:
            await asyncio.wait_for(worker_task, timeout=6.0)
        except asyncio.TimeoutError:
            logger.warning("Transcription worker timed out after 6s for question=%s", question_id)
            worker_task.cancel()
        except asyncio.CancelledError:
            pass
        except Exception as fin_err:
            logger.warning("Error waiting for transcription worker: %s", fin_err)

        logger.info("STT WebSocket closed for question=%s", question_id)


@router.get("/api/stt/vad-presets", summary="Get Gnani VAD tuning presets and parameters")
def get_gnani_vad_presets():
    """Retrieve official Gnani Voice Activity Detection (VAD) tuning presets and parameters."""
    return {
        "presets": GNANI_VAD_PRESETS,
        "default_preset": "interview_optimal",
        "parameters": {
            "vad_threshold": {
                "header": "x-vad-threshold",
                "name": "Speech Probability Threshold",
                "description": "How confident the neural net must be that a frame contains speech. Higher values reject background noise; lower values catch quiet speech.",
                "default": 0.55,
                "min": 0.0,
                "max": 1.0,
                "step": 0.05,
                "unit": "ratio",
                "recommended_clean": 0.55,
                "recommended_noisy": 0.72
            },
            "min_silence_ms": {
                "header": "x-min-silence-ms",
                "name": "Silence Required to Close Segment",
                "description": "Milliseconds of silence after speech before closing segment and transcribing. Controls turn-taking latency vs. sentence completeness.",
                "default": 700,
                "min": 100,
                "max": 2000,
                "step": 50,
                "unit": "ms",
                "recommended_fast": 350,
                "recommended_conversational": 700
            },
            "min_speech_ms": {
                "header": "x-min-speech-ms",
                "name": "Speech Required to Open Segment",
                "description": "Noise gate at start of speech. Consecutive speech needed before opening a segment. Suppresses coughs, clicks, and breathing noises.",
                "default": 120,
                "min": 50,
                "max": 2000,
                "step": 25,
                "unit": "ms",
                "recommended_clean": 120,
                "recommended_noisy": 220
            },
            "min_segment_ms": {
                "header": "x-min-segment-ms",
                "name": "Minimum Confirmed Segment Length",
                "description": "Floor on the speech required to confirm a segment. Suppresses stray sounds while preserving genuine short technical terms.",
                "default": 120,
                "min": 100,
                "max": 1000,
                "step": 20,
                "unit": "ms"
            },
            "max_speech_s": {
                "header": "x-max-speech-s",
                "name": "Monologue Forced Segment Cap",
                "description": "Hard cap on continuous uninterrupted speech before force-closing segment so intermediate transcripts keep flowing during long explanations.",
                "default": 20.0,
                "min": 5.0,
                "max": 120.0,
                "step": 5.0,
                "unit": "s",
                "recommended_interview": 20.0
            }
        }
    }


@router.websocket("/ws/stt/{language_code}")
async def websocket_stt_endpoint(
    websocket: WebSocket,
    language_code: str = "unknown",
    assessment_id: Optional[str] = Query(None),
    question_id: Optional[str] = Query(None),
    provider: Optional[str] = Query("sarvam"),
    preset: str = Query("interview_optimal"),
    vad_threshold: float = Query(settings.GNANI_VAD_THRESHOLD, ge=0.0, le=1.0),
    min_silence_ms: int = Query(settings.GNANI_MIN_SILENCE_MS, ge=100, le=2000),
    min_speech_ms: int = Query(settings.GNANI_MIN_SPEECH_MS, ge=50, le=2000),
    min_segment_ms: int = Query(settings.GNANI_MIN_SEGMENT_MS, ge=100, le=1000),
    max_speech_s: float = Query(settings.GNANI_MAX_SPEECH_S, ge=5.0, le=120.0),
):
    await handle_websocket_stt(
        websocket=websocket,
        language_code=language_code,
        assessment_id=assessment_id,
        question_id=question_id,
        provider=provider,
        preset=preset,
        vad_threshold=vad_threshold,
        min_silence_ms=min_silence_ms,
        min_speech_ms=min_speech_ms,
        min_segment_ms=min_segment_ms,
        max_speech_s=max_speech_s
    )


@router.websocket("/ws/stt/{language_code}/")
async def websocket_stt_endpoint_slash(
    websocket: WebSocket,
    language_code: str = "unknown",
    assessment_id: Optional[str] = Query(None),
    question_id: Optional[str] = Query(None),
    provider: Optional[str] = Query("sarvam"),
    preset: str = Query("interview_optimal"),
    vad_threshold: float = Query(settings.GNANI_VAD_THRESHOLD, ge=0.0, le=1.0),
    min_silence_ms: int = Query(settings.GNANI_MIN_SILENCE_MS, ge=100, le=2000),
    min_speech_ms: int = Query(settings.GNANI_MIN_SPEECH_MS, ge=50, le=2000),
    min_segment_ms: int = Query(settings.GNANI_MIN_SEGMENT_MS, ge=100, le=1000),
    max_speech_s: float = Query(settings.GNANI_MAX_SPEECH_S, ge=5.0, le=120.0),
):
    await handle_websocket_stt(
        websocket=websocket,
        language_code=language_code,
        assessment_id=assessment_id,
        question_id=question_id,
        provider=provider,
        preset=preset,
        vad_threshold=vad_threshold,
        min_silence_ms=min_silence_ms,
        min_speech_ms=min_speech_ms,
        min_segment_ms=min_segment_ms,
        max_speech_s=max_speech_s
    )


@router.post("/api/stt/transcribe")
async def transcribe_audio_file(
    file: UploadFile = File(...),
    language_code: str = Query("unknown"),
    model: str = Query("saaras:v4"),
    question_id: Optional[str] = Query(None),
    provider: Optional[str] = Query("sarvam")
):
    """Direct audio file transcription endpoint supporting Sarvam and Gnani."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    if provider and provider.lower() == "gnani":
        if not is_gnani_configured():
            raise HTTPException(status_code=500, detail="Gnani AI API key (GNANI_API_KEY) is not configured.")
        try:
            gnani_lang = "indic-auto" if (not language_code or language_code.lower() in ("unknown", "auto", "default", "indic-auto")) else language_code
            result = await transcribe_audio_file_gnani(
                audio_bytes=content,
                language_code=gnani_lang,
                format="transcribe"
            )
            return {
                "transcript": result["transcript"],
                "latencyMs": result["latency_ms"],
                "provider": "gnani",
                "model": result.get("model", "gnani-prisma-v2.5"),
                "language_code": result.get("language_code", gnani_lang),
                "question_id": question_id
            }
        except Exception as err:
            logger.error("Gnani REST transcribe error: %s", err)
            raise HTTPException(status_code=500, detail=str(err))

    adapter = SarvamSTTAdapter()
    if not adapter.is_configured():
        raise HTTPException(status_code=500, detail="Sarvam AI API key (SARVAM_API_KEY) is not configured.")

    filename = file.filename or "audio.wav"
    raw_content_type = file.content_type or "audio/wav"
    content_type = raw_content_type.split(";")[0].strip()
    if not content_type or content_type == "application/octet-stream":
        content_type = "audio/webm" if "webm" in filename else "audio/wav"

    try:
        sarvam_lang = "unknown" if (not language_code or language_code.lower() in ("unknown", "auto", "default")) else language_code
        result = await asyncio.to_thread(
            adapter.transcribe_audio_bytes,
            content,
            filename=filename,
            language_code=sarvam_lang,
            mime_type=content_type,
            model=model,
            mode="transcribe"
        )
        return {
            "transcript": result["transcript"],
            "latencyMs": result["latency_ms"],
            "provider": "sarvam",
            "model": result.get("model", model),
            "language_code": result.get("language_code", sarvam_lang),
            "question_id": question_id
        }
    except Exception as err:
        logger.error("REST transcribe error: %s", err)
        raise HTTPException(status_code=500, detail=str(err))
