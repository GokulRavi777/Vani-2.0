"""WebSocket router for real-time STT streaming (Google STT, Sarvam AI, and Compare mode)."""

import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.services.stt.base import (
    GoogleSTTAdapter,
    SarvamSTTAdapter,
    STTBenchmarkOrchestrator
)

logger = logging.getLogger("stt_router")

router = APIRouter(tags=["STT Streaming"])


@router.websocket("/ws/stt/{language_code}")
@router.websocket("/ws/stt/{language_code}/")
async def websocket_stt_endpoint(
    websocket: WebSocket,
    language_code: str = "en-IN",
    assessment_id: Optional[str] = Query(None),
    question_id: Optional[str] = Query(None),
    provider: Optional[str] = Query("google")
):
    await websocket.accept()
    logger.info(
        "WebSocket STT connected: lang=%s, assessment=%s, question=%s, provider=%s",
        language_code, assessment_id, question_id, provider
    )

    audio_queue: asyncio.Queue = asyncio.Queue()

    # Determine provider adapter
    selected_mode = (provider or "google").lower()
    google_adapter = GoogleSTTAdapter()
    sarvam_adapter = SarvamSTTAdapter()

    # Check configuration
    if selected_mode == "google" and not google_adapter.is_configured():
        await websocket.send_json({
            "type": "error",
            "provider": "google",
            "question_id": question_id,
            "error": "Google Cloud STT credentials (GOOGLE_APPLICATION_CREDENTIALS) are not configured on the backend."
        })
    elif selected_mode == "sarvam" and not sarvam_adapter.is_configured():
        await websocket.send_json({
            "type": "error",
            "provider": "sarvam",
            "question_id": question_id,
            "error": "Sarvam AI API key (SARVAM_API_KEY) is not configured on the backend."
        })
    elif selected_mode == "compare":
        if not google_adapter.is_configured() and not sarvam_adapter.is_configured():
            await websocket.send_json({
                "type": "error",
                "provider": "compare",
                "question_id": question_id,
                "error": "Backend credentials missing: Neither GOOGLE_APPLICATION_CREDENTIALS nor SARVAM_API_KEY is configured."
            })

    async def audio_stream_generator():
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                break
            yield chunk

    async def run_transcription_worker():
        try:
            if selected_mode == "google" and google_adapter.is_configured():
                async for event in google_adapter.transcribe_stream(audio_stream_generator(), language_code=language_code):
                    msg_type = "final" if event.get("is_final") else "partial"
                    await websocket.send_json({
                        "type": msg_type,
                        "transcript": event.get("transcript", ""),
                        "question_id": question_id,
                        "provider": "google",
                        "latencyMs": event.get("latency_ms")
                    })
            elif selected_mode == "sarvam" and sarvam_adapter.is_configured():
                async for event in sarvam_adapter.transcribe_stream(audio_stream_generator(), language_code=language_code):
                    msg_type = "final" if event.get("is_final") else "partial"
                    await websocket.send_json({
                        "type": msg_type,
                        "transcript": event.get("transcript", ""),
                        "question_id": question_id,
                        "provider": "sarvam",
                        "latencyMs": event.get("latency_ms")
                    })
            elif selected_mode == "compare":
                # In compare mode, route to both active configured providers
                tasks = []
                if google_adapter.is_configured():
                    async def run_google():
                        async for event in google_adapter.transcribe_stream(audio_stream_generator(), language_code=language_code):
                            msg_type = "final" if event.get("is_final") else "partial"
                            await websocket.send_json({
                                "type": msg_type,
                                "transcript": event.get("transcript", ""),
                                "question_id": question_id,
                                "provider": "google",
                                "latencyMs": event.get("latency_ms")
                            })
                    tasks.append(asyncio.create_task(run_google()))

                if sarvam_adapter.is_configured():
                    async def run_sarvam():
                        async for event in sarvam_adapter.transcribe_stream(audio_stream_generator(), language_code=language_code):
                            msg_type = "final" if event.get("is_final") else "partial"
                            await websocket.send_json({
                                "type": msg_type,
                                "transcript": event.get("transcript", ""),
                                "question_id": question_id,
                                "provider": "sarvam",
                                "latencyMs": event.get("latency_ms")
                            })
                    tasks.append(asyncio.create_task(run_sarvam()))

                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.warning("Transcription worker error: %s", str(e))
            try:
                await websocket.send_json({
                    "type": "error",
                    "provider": selected_mode,
                    "question_id": question_id,
                    "error": str(e)
                })
            except Exception:
                pass

    worker_task = asyncio.create_task(run_transcription_worker())

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            
            # Binary chunk from AudioCaptureService (16kHz PCM Int16)
            bytes_data = message.get("bytes")
            if bytes_data:
                await audio_queue.put(bytes_data)
            elif message.get("text"):
                # Potential control message (e.g. stop)
                text = message.get("text")
                if text in ("stop", "end"):
                    await audio_queue.put(None)
    except WebSocketDisconnect:
        logger.info("WebSocket STT disconnected normally by client")
    except Exception as e:
        logger.error("WebSocket receive loop error: %s", str(e))
    finally:
        await audio_queue.put(None)
        worker_task.cancel()
