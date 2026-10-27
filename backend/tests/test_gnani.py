"""Tests for Gnani Voice Integration using official pipecat-gnani plugin."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.gnani_service import SUPPORTED_GNANI_VOICES
try:
    from pipecat.frames.frames import TranscriptionFrame, TTSAudioRawFrame
except ImportError:
    from app.services.gnani_service import TranscriptionFrame, TTSAudioRawFrame

client = TestClient(app)


def test_get_gnani_voices():
    """Verify that GET /api/tts/voices returns verified Gnani voices catalog."""
    res = client.get("/api/tts/voices?provider=gnani")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "gnani"
    assert "voices" in data
    assert len(data["voices"]) >= 10
    
    # Check default voice Pranav is present
    pranav = next((v for v in data["voices"] if v["id"] == "Pranav"), None)
    assert pranav is not None
    assert pranav["gender"] == "Male"
    assert pranav["language"] == "en-IN"

    # Check Kaveri female voice
    kaveri = next((v for v in data["voices"] if v["id"] == "Kaveri"), None)
    assert kaveri is not None
    assert kaveri["gender"] == "Female"


def test_synthesize_unconfigured_gnani_returns_400(monkeypatch):
    """Verify clean 400 error when GNANI_API_KEY is not set."""
    monkeypatch.setattr("app.services.gnani_service.get_gnani_api_key", lambda: None)
    res = client.post(
        "/api/tts/synthesize",
        json={"text": "What is Python?", "voice": "Pranav", "provider": "gnani"}
    )
    assert res.status_code == 400
    assert "GNANI_API_KEY" in res.json()["detail"]


@pytest.mark.anyio
async def test_synthesize_success_with_mocked_pipecat_service(monkeypatch):
    """Verify that synthesize endpoint produces WAV audio bytes using GnaniHttpTTSService."""
    monkeypatch.setattr("app.services.gnani_service.get_gnani_api_key", lambda: "mock-gnani-key")

    mock_pcm = b"\x00\x00" * 8000  # 0.5s of 16kHz silence

    async def mock_run_tts(self, text, context_id="ctx"):
        yield TTSAudioRawFrame(audio=mock_pcm, sample_rate=16000, num_channels=1)

    with patch("pipecat_gnani.tts.GnaniHttpTTSService.run_tts", mock_run_tts):
        res = client.post(
            "/api/tts/synthesize",
            json={"text": "What is a list in Python?", "voice": "Pranav", "provider": "gnani"}
        )
        assert res.status_code == 200
        assert res.headers["content-type"] == "audio/wav"
        assert res.content[:4] == b"RIFF"
        assert res.content[8:12] == b"WAVE"


def test_websocket_stt_unconfigured_gnani_returns_error(monkeypatch):
    """Verify that WebSocket endpoint returns clean JSON error when GNANI_API_KEY is not set."""
    monkeypatch.setattr("app.services.gnani_service.get_gnani_api_key", lambda: None)

    with client.websocket_connect("/ws/stt/en-IN?provider=gnani&question_id=py_q1") as websocket:
        data = websocket.receive_json()
        assert data["type"] == "error"
        assert data["provider"] == "gnani"
        assert "GNANI_API_KEY" in data["error"]


@pytest.mark.anyio
async def test_rest_transcribe_gnani_unconfigured(monkeypatch):
    """Verify that REST transcribe returns error when Gnani is unconfigured."""
    monkeypatch.setattr("app.services.gnani_service.get_gnani_api_key", lambda: None)
    files = {"file": ("audio.wav", b"dummy-content", "audio/wav")}
    res = client.post("/api/stt/transcribe?provider=gnani&language_code=en-IN", files=files)
    assert res.status_code == 500
    assert "GNANI_API_KEY" in res.json()["detail"]


@pytest.mark.anyio
async def test_rest_transcribe_gnani_success(monkeypatch):
    """Verify that REST transcribe returns transcript from GnaniHttpSTTService."""
    monkeypatch.setattr("app.services.gnani_service.get_gnani_api_key", lambda: "mock-gnani-key")

    async def mock_run_stt(self, audio):
        yield TranscriptionFrame(text="A list is mutable while a tuple is immutable.", user_id="user", timestamp="")

    with patch("pipecat_gnani.stt.GnaniHttpSTTService.run_stt", mock_run_stt):
        files = {"file": ("audio.wav", b"RIFF....WAVEfmt ....data....", "audio/wav")}
        res = client.post("/api/stt/transcribe?provider=gnani&language_code=en-IN&question_id=py_q1", files=files)
        assert res.status_code == 200
        payload = res.json()
        assert payload["provider"] == "gnani"
        assert payload["transcript"] == "A list is mutable while a tuple is immutable."
        assert payload["question_id"] == "py_q1"


@pytest.mark.anyio
async def test_rest_transcribe_gnani_auto_detect(monkeypatch):
    """Verify that REST transcribe with unknown/auto language code defaults to indic-auto."""
    monkeypatch.setattr("app.services.gnani_service.get_gnani_api_key", lambda: "mock-gnani-key")

    async def mock_run_stt(self, audio):
        yield TranscriptionFrame(text="பட்டியல் மாறக்கூடியது ஆனால் டூப்பிள் மாறாதது.", user_id="user", timestamp="")

    with patch("pipecat_gnani.stt.GnaniHttpSTTService.run_stt", mock_run_stt):
        files = {"file": ("audio.wav", b"RIFF....WAVEfmt ....data....", "audio/wav")}
        res = client.post("/api/stt/transcribe?provider=gnani&language_code=unknown&question_id=py_q2", files=files)
        assert res.status_code == 200
        payload = res.json()
        assert payload["provider"] == "gnani"
        assert payload["transcript"] == "பட்டியல் மாறக்கூடியது ஆனால் டூப்பிள் மாறாதது."
        assert payload["language_code"] == "indic-auto"
        assert payload["question_id"] == "py_q2"


def test_synthesize_unsupported_voice_returns_400(monkeypatch):
    """Verify that requesting an unsupported voice returns HTTP 400."""
    monkeypatch.setattr("app.services.gnani_service.get_gnani_api_key", lambda: "mock-key")
    res = client.post(
        "/api/tts/synthesize",
        json={"text": "Hello world", "voice": "NonExistentVoice_XYZ", "provider": "gnani"}
    )
    assert res.status_code == 400
    assert "Unsupported voice" in res.json()["detail"]


@pytest.mark.anyio
async def test_synthesize_api_error_returns_502(monkeypatch):
    """Verify that upstream Gnani TTS errors return HTTP 502."""
    monkeypatch.setattr("app.services.gnani_service.get_gnani_api_key", lambda: "mock-key")

    async def mock_fail_tts(self, text, context_id="ctx"):
        from pipecat.frames.frames import ErrorFrame
        yield ErrorFrame(error="Gnani upstream inference timeout (504)")

    with patch("pipecat_gnani.tts.GnaniHttpTTSService.run_tts", mock_fail_tts):
        res = client.post(
            "/api/tts/synthesize",
            json={"text": "What is SQL?", "voice": "Pranav", "provider": "gnani"}
        )
        assert res.status_code == 502
        assert "Gnani TTS synthesis failed" in res.json()["detail"]


@pytest.mark.anyio
async def test_question_audio_session_navigation_and_persistence(monkeypatch):
    """Verify question audio synthesis, voice persistence across Q1 and Q2, and caching."""
    monkeypatch.setattr("app.services.gnani_service.get_gnani_api_key", lambda: "mock-key")

    mock_pcm = b"\x00\x00" * 4000

    async def mock_run_tts(self, text, context_id="ctx"):
        yield TTSAudioRawFrame(audio=mock_pcm, sample_rate=16000, num_channels=1)

    # 1. Create an assessment session with Gnani provider and selected voice
    create_res = client.post(
        "/api/assessments",
        json={
            "skills": ["Python"],
            "language": "en-IN",
            "question_count": 2,
            "provider": "gnani",
            "voice": "Kaveri"
        }
    )
    assert create_res.status_code == 201
    assessment = create_res.json()
    asm_id = assessment["assessment_id"]
    assert assessment["provider"] == "gnani"
    assert assessment["voice"] == "Kaveri"
    assert len(assessment["questions"]) == 2
    q1_id = assessment["questions"][0]["question_id"]
    q2_id = assessment["questions"][1]["question_id"]

    with patch("pipecat_gnani.tts.GnaniHttpTTSService.run_tts", mock_run_tts):
        # 2. Fetch Question 1 audio (reads aloud using persisted Kaveri voice)
        q1_res = client.get(f"/api/tts/assessments/{asm_id}/questions/{q1_id}")
        assert q1_res.status_code == 200
        assert q1_res.headers["content-type"] == "audio/wav"
        assert q1_res.content[:4] == b"RIFF"

        # 3. Navigate to Question 2 and fetch audio (reuses persisted session voice)
        q2_res = client.get(f"/api/tts/assessments/{asm_id}/questions/{q2_id}")
        assert q2_res.status_code == 200
        assert q2_res.headers["content-type"] == "audio/wav"

        # 4. Navigate back to Question 1: audio is served from cache
        q1_cached = client.get(f"/api/tts/assessments/{asm_id}/questions/{q1_id}")
        assert q1_cached.status_code == 200
        assert q1_cached.content == q1_res.content

        # 5. Invalid question ID returns 404
        invalid_q = client.get(f"/api/tts/assessments/{asm_id}/questions/invalid_q_999")
        assert invalid_q.status_code == 404

        # 6. Invalid assessment ID returns 404
        invalid_asm = client.get(f"/api/tts/assessments/asm_nonexistent/questions/{q1_id}")
        assert invalid_asm.status_code == 404


def test_get_vad_presets_endpoint():
    """Verify GET /api/stt/vad-presets returns presets and valid parameter specs."""
    res = client.get("/api/stt/vad-presets")
    assert res.status_code == 200
    data = res.json()
    assert "presets" in data
    assert "parameters" in data
    assert "interview_optimal" in data["presets"]
    assert "fast_turnaround" in data["presets"]
    assert "noisy_room" in data["presets"]
    assert "monologue_heavy" in data["presets"]
    assert data["parameters"]["vad_threshold"]["default"] == 0.55


def test_build_gnani_vad_headers_clamping():
    """Verify that build_gnani_vad_headers clamps out-of-range values to documented limits."""
    from app.services.gnani_service import build_gnani_vad_headers

    # Exceeding bounds: threshold > 1.0, silence > 2000, speech < 50
    headers = build_gnani_vad_headers(
        api_key="test-api-key",
        vad_threshold=1.5,
        min_silence_ms=9999,
        min_speech_ms=10,
        min_segment_ms=50,
        max_speech_s=200.0,
        enable_word_boosting=True
    )
    assert headers["x-vad-threshold"] == "1.00"
    assert headers["x-min-silence-ms"] == "2000"
    assert headers["x-min-speech-ms"] == "50"
    assert headers["x-min-segment-ms"] == "100"
    assert headers["x-max-speech-s"] == "120.0"
    assert "Python" in headers["x-bias-list"]
    assert headers["x-bias-score"] == "1.5"
    assert headers["x-api-key-id"] == "test-api-key"


@pytest.mark.anyio
async def test_gnani_realtime_client_state_and_framing():
    """Verify GnaniRealtimeSTTClient connection state handling and 1024-byte framing."""
    try:
        from websockets.protocol import State
    except ImportError:
        from websockets import State  # type: ignore
    from app.services.gnani_service import GnaniRealtimeSTTClient

    client = GnaniRealtimeSTTClient(api_key="mock-key")
    assert not client.is_ws_open

    # Mock websockets ClientConnection object with State enum
    class MockWS:
        def __init__(self, state):
            self.state = state

    client.ws = MockWS(State.OPEN)
    assert client.is_ws_open is True

    client.ws = MockWS(State.CLOSED)
    assert client.is_ws_open is False

    # Verify 1,024-byte framing
    # Send 500 bytes: should remain buffered, queue empty
    await client.send_audio_chunk(b"\x01" * 500)
    assert client._audio_queue.empty()

    # Send 600 bytes (total 1100 bytes): should flush exactly 1,024 bytes and keep 76 in buffer
    await client.send_audio_chunk(b"\x02" * 600)
    frame = await client._audio_queue.get()
    assert len(frame) == 1024
    assert len(client._buffer) == 76

