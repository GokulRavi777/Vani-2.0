"""Tests for Phase 4 Gnani Voice Cloning and Custom Voice Question Synthesis."""

import io
import wave
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.custom_voice_store import get_custom_voice_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_custom_voice_store():
    """Ensure clean custom voice store for each test."""
    store = get_custom_voice_store()
    store.clear()
    yield
    store.clear()


def create_dummy_wav_bytes(duration_sec: float = 1.0, sample_rate: int = 16000) -> bytes:
    """Create a minimal valid WAV container with audio frames."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * int(sample_rate * duration_sec))
    return buf.getvalue()


def test_enroll_without_consent_returns_400():
    """Verify that voice enrollment strictly rejects requests without explicit user consent."""
    audio = create_dummy_wav_bytes()
    files = {"file": ("my_sample.wav", audio, "audio/wav")}
    data = {"voice_name": "My Voice", "consent": "false"}

    res = client.post("/api/tts/voice-clone/enroll", files=files, data=data)
    assert res.status_code == 400
    assert "consent" in res.json()["detail"].lower()


def test_enroll_empty_audio_returns_400():
    """Verify that uploading an empty audio file returns 400."""
    files = {"file": ("empty.wav", b"", "audio/wav")}
    data = {"voice_name": "My Voice", "consent": "true"}

    res = client.post("/api/tts/voice-clone/enroll", files=files, data=data)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_enroll_unsupported_audio_format_returns_400():
    """Verify that uploading an unsupported file format returns 400."""
    files = {"file": ("notes.txt", b"A" * 5000, "text/plain")}
    data = {"voice_name": "My Voice", "consent": "true"}

    res = client.post("/api/tts/voice-clone/enroll", files=files, data=data)
    assert res.status_code == 400
    assert "unsupported audio format" in res.json()["detail"].lower()


def test_enroll_unconfigured_gnani_returns_400(monkeypatch):
    """Verify that enrollment returns a clear 400 error when GNANI_API_KEY is missing."""
    monkeypatch.setattr("app.services.voice_cloning_service.get_gnani_api_key", lambda: None)
    audio = create_dummy_wav_bytes(duration_sec=2.0)
    files = {"file": ("my_sample.wav", audio, "audio/wav")}
    data = {"voice_name": "My Voice", "consent": "true"}

    res = client.post("/api/tts/voice-clone/enroll", files=files, data=data)
    assert res.status_code == 400
    assert "GNANI_API_KEY" in res.json()["detail"]


def test_enroll_success_and_persisted(monkeypatch):
    """Verify that successful enrollment persists the voice embedding and returns custom voice ID."""
    monkeypatch.setattr("app.services.voice_cloning_service.get_gnani_api_key", lambda: "mock-key")

    mock_gnani_response = MagicMock()
    mock_gnani_response.status_code = 200
    mock_gnani_response.json.return_value = {
        "success": True,
        "message": "Voice embeddings generated successfully",
        "data": {
            "voice_clone_embedding": {
                "embedding": "MOCK_EMBEDDING_VECTOR_DATA_XYZ",
                "shape": [1, 768],
                "dtype": "torch.bfloat16"
            }
        }
    }

    with patch("requests.post", return_value=mock_gnani_response):
        audio = create_dummy_wav_bytes(duration_sec=2.0)
        files = {"file": ("my_sample.wav", audio, "audio/wav")}
        data = {"voice_name": "Gokul Voice", "consent": "true"}

        res = client.post("/api/tts/voice-clone/enroll", files=files, data=data)
        assert res.status_code == 201
        payload = res.json()
        assert payload["success"] is True
        voice_data = payload["voice"]
        assert voice_data["voice_id"].startswith("cloned_voice_")
        assert voice_data["name"] == "Gokul Voice"
        assert voice_data["embedding_shape"] == [1, 768]

        # Verify voice is saved in custom voice store
        store = get_custom_voice_store()
        saved = store.get_voice(voice_data["voice_id"])
        assert saved is not None
        assert saved["speaker_embedding"]["embedding"] == "MOCK_EMBEDDING_VECTOR_DATA_XYZ"


def test_enrolled_voice_in_get_voices_list():
    """Verify that enrolled custom voice appears in GET /api/tts/voices alongside standard voices."""
    store = get_custom_voice_store()
    store.save_voice(
        voice_id="cloned_voice_test_123",
        name="Candidate Voice",
        speaker_embedding={"embedding": "test_vec", "shape": [1, 768], "dtype": "torch.bfloat16"}
    )

    res = client.get("/api/tts/voices?provider=gnani")
    assert res.status_code == 200
    data = res.json()
    assert data["provider"] == "gnani"
    voices = data["voices"]

    # Verify custom voice is present
    custom_voice = next((v for v in voices if v["id"] == "cloned_voice_test_123"), None)
    assert custom_voice is not None
    assert "Candidate Voice" in custom_voice["name"]
    assert custom_voice.get("is_custom") is True

    # Verify standard voices remain available as fallback
    assert any(v["id"] == "Kaveri" for v in voices)
    assert any(v["id"] == "Pranav" for v in voices)


@pytest.mark.anyio
async def test_synthesize_with_custom_voice_id(monkeypatch):
    """Verify that synthesizing with custom voice ID uses vachana-vc-v1 and speaker_embedding."""
    monkeypatch.setattr("app.services.gnani_service.get_gnani_api_key", lambda: "mock-key")

    store = get_custom_voice_store()
    store.save_voice(
        voice_id="cloned_voice_test_123",
        name="Candidate Voice",
        speaker_embedding={"embedding": "mock_emb", "shape": [1, 768], "dtype": "torch.bfloat16"}
    )

    mock_wav = create_dummy_wav_bytes(duration_sec=1.5)

    async def mock_cloned_synth(text, speaker_embedding, sample_rate=16000):
        assert speaker_embedding["embedding"] == "mock_emb"
        assert "Python" in text
        return mock_wav

    with patch("app.services.gnani_service.synthesize_cloned_voice_speech", mock_cloned_synth):
        res = client.post(
            "/api/tts/synthesize",
            json={
                "text": "What is Python?",
                "voice": "cloned_voice_test_123",
                "provider": "gnani"
            }
        )
        assert res.status_code == 200
        assert res.headers["content-type"] == "audio/wav"
        assert res.content[:4] == b"RIFF"


@pytest.mark.anyio
async def test_custom_voice_fallback_to_standard_on_error(monkeypatch):
    """Verify that when custom cloned synthesis fails, it gracefully falls back to standard voice."""
    monkeypatch.setattr("app.services.gnani_service.get_gnani_api_key", lambda: "mock-key")

    store = get_custom_voice_store()
    store.save_voice(
        voice_id="cloned_voice_broken",
        name="Broken Voice",
        speaker_embedding={"embedding": "bad_emb", "shape": [1, 768], "dtype": "torch.bfloat16"}
    )

    fallback_wav = create_dummy_wav_bytes(duration_sec=1.0)

    async def mock_fail_cloned(text, speaker_embedding, sample_rate=16000):
        raise RuntimeError("Gnani voice clone model temporary error 500")

    async def mock_standard_speech(text, voice, language_code="en-IN", sample_rate=16000):
        # Successfully served via standard voice fallback
        return fallback_wav

    with patch("app.services.gnani_service.synthesize_cloned_voice_speech", mock_fail_cloned), \
         patch("app.services.gnani_service.synthesize_question_speech", mock_standard_speech):

        res = client.post(
            "/api/tts/synthesize",
            json={
                "text": "Explain recursion in programming.",
                "voice": "cloned_voice_broken",
                "provider": "gnani"
            }
        )
        assert res.status_code == 200
        assert res.headers["content-type"] == "audio/wav"
        assert res.content == fallback_wav


def test_delete_enrolled_voice():
    """Verify deleting an enrolled custom voice."""
    store = get_custom_voice_store()
    store.save_voice(
        voice_id="cloned_voice_to_delete",
        name="Temporary Voice",
        speaker_embedding={"embedding": "del_emb", "shape": [1, 768], "dtype": "torch.bfloat16"}
    )

    del_res = client.delete("/api/tts/voice-clone/voices/cloned_voice_to_delete")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Voice should now be gone
    assert store.get_voice("cloned_voice_to_delete") is None

    # Deleting non-existent returns 404
    not_found_res = client.delete("/api/tts/voice-clone/voices/cloned_voice_to_delete")
    assert not_found_res.status_code == 404
