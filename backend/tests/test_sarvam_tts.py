import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.tts.sarvam_adapter import SarvamTTSAdapter, SUPPORTED_SARVAM_VOICES

client = TestClient(app)


def test_sarvam_voices_endpoint():
    response = client.get("/api/tts/voices?provider=sarvam")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "sarvam"
    assert data["default_voice"] == "shubh"
    assert len(data["voices"]) >= 10
    voice_ids = [v["id"] for v in data["voices"]]
    assert "shubh" in voice_ids
    assert "ritu" in voice_ids


def test_sarvam_tts_adapter_voices():
    voices = SarvamTTSAdapter.get_supported_voices()
    assert len(voices) >= 10
    assert any(v["id"] == "shubh" for v in voices)
    assert any(v["id"] == "ritu" for v in voices)


@pytest.mark.anyio
async def test_sarvam_synthesize_endpoint_mock():
    with patch("app.services.tts.sarvam_adapter.SarvamTTSAdapter.synthesize") as mock_synth:
        mock_synth.return_value = b"RIFFmockwavcontent"
        response = client.post("/api/tts/synthesize", json={
            "text": "What is Python?",
            "voice": "shubh",
            "provider": "sarvam"
        })
        assert response.status_code == 200
        assert response.headers["content-type"] == "audio/wav"
        assert response.content == b"RIFFmockwavcontent"
