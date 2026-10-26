"""STT Router for Sarvam AI Saaras v4 transcription.

Supports:
1. Real-time WebSocket streaming with live partials and final transcript
2. REST audio upload endpoint (POST /api/stt/transcribe) for direct audio blobs
"""

import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, UploadFile, File, HTTPException

from app.services.stt.base import SarvamSTTAdapter

logger = logging.getLogger("stt_router")

router = APIRouter(tags=["STT Streaming"])


async def handle_websocket_stt(
    websocket: WebSocket,
    language_code: str = "unknown",
    assessment_id: Optional[str] = None,
    question_id: Optional[str] = None,
    provider: Optional[str] = "sarvam"
):
    await websocket.accept()
    logger.info(
        "WebSocket STT connected: lang=%s, assessment=%s, question=%s, provider=%s",
        language_code, assessment_id, question_id, provider
    )

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
            logger.info("Starting Sarvam transcription for question=%s", question_id)
            event_count = 0
            async for event in adapter.transcribe_stream(
                audio_stream_generator(), language_code=language_code
            ):
                event_count += 1
                msg_type = "final" if event.get("is_final") else "partial"
                transcript = event.get("transcript", "")
                logger.info(
                    "Transcript event #%d type=%s text=%r latency=%.0fms",
                    event_count, msg_type, transcript, event.get("latency_ms", 0)
                )
                try:
                    await websocket.send_json({
                        "type": msg_type,
                        "transcript": transcript,
                        "question_id": question_id,
                        "provider": "sarvam",
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


@router.websocket("/ws/stt/{language_code}")
async def websocket_stt_endpoint(
    websocket: WebSocket,
    language_code: str = "unknown",
    assessment_id: Optional[str] = Query(None),
    question_id: Optional[str] = Query(None),
    provider: Optional[str] = Query("sarvam")
):
    await handle_websocket_stt(websocket, language_code, assessment_id, question_id, provider)


@router.websocket("/ws/stt/{language_code}/")
async def websocket_stt_endpoint_slash(
    websocket: WebSocket,
    language_code: str = "unknown",
    assessment_id: Optional[str] = Query(None),
    question_id: Optional[str] = Query(None),
    provider: Optional[str] = Query("sarvam")
):
    await handle_websocket_stt(websocket, language_code, assessment_id, question_id, provider)


@router.post("/api/stt/transcribe")
async def transcribe_audio_file(
    file: UploadFile = File(...),
    language_code: str = Query("unknown"),
    model: str = Query("saaras:v4"),
    question_id: Optional[str] = Query(None)
):
    """Direct audio file transcription endpoint using Sarvam AI Saaras v4."""
    adapter = SarvamSTTAdapter()
    if not adapter.is_configured():
        raise HTTPException(status_code=500, detail="Sarvam AI API key (SARVAM_API_KEY) is not configured.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded audio file is empty.")

    filename = file.filename or "audio.wav"
    raw_content_type = file.content_type or "audio/wav"
    content_type = raw_content_type.split(";")[0].strip()
    if not content_type or content_type == "application/octet-stream":
        content_type = "audio/webm" if "webm" in filename else "audio/wav"


    try:
        result = await asyncio.to_thread(
            adapter.transcribe_audio_bytes,
            content,
            filename=filename,
            language_code=language_code,
            mime_type=content_type,
            model=model
        )
        return {
            "transcript": result["transcript"],
            "latencyMs": result["latency_ms"],
            "provider": "sarvam",
            "model": result.get("model", model),
            "question_id": question_id
        }
    except Exception as err:
        logger.error("REST transcribe error: %s", err)
        raise HTTPException(status_code=500, detail=str(err))
