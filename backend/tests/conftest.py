import sys
import types
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

# Provide mock modules if pipecat / pipecat_gnani are not installed in the environment
if "pipecat_gnani" not in sys.modules:
    mock_gnani_pkg = types.ModuleType("pipecat_gnani")
    mock_stt_mod = types.ModuleType("pipecat_gnani.stt")
    mock_tts_mod = types.ModuleType("pipecat_gnani.tts")

    class GnaniHttpTTSService:
        class Settings:
            def __init__(self, *args, **kwargs): pass
        def __init__(self, *args, **kwargs): pass
        async def run_tts(self, *args, **kwargs):
            if False: yield None

    class GnaniHttpSTTService:
        class Settings:
            def __init__(self, *args, **kwargs): pass
        def __init__(self, *args, **kwargs): pass
        async def run_stt(self, *args, **kwargs):
            if False: yield None

    class GnaniSTTService:
        pass

    mock_tts_mod.GnaniHttpTTSService = GnaniHttpTTSService
    mock_stt_mod.GnaniHttpSTTService = GnaniHttpSTTService
    mock_stt_mod.GnaniSTTService = GnaniSTTService
    mock_gnani_pkg.stt = mock_stt_mod
    mock_gnani_pkg.tts = mock_tts_mod
    mock_gnani_pkg.GnaniHttpTTSService = GnaniHttpTTSService
    mock_gnani_pkg.GnaniHttpSTTService = GnaniHttpSTTService
    mock_gnani_pkg.GnaniSTTService = GnaniSTTService

    sys.modules["pipecat_gnani"] = mock_gnani_pkg
    sys.modules["pipecat_gnani.stt"] = mock_stt_mod
    sys.modules["pipecat_gnani.tts"] = mock_tts_mod

if "pipecat" not in sys.modules:
    mock_pipecat = types.ModuleType("pipecat")
    frames_mod = types.ModuleType("pipecat.frames")
    frames_frames_mod = types.ModuleType("pipecat.frames.frames")

    class Frame:
        pass

    class ErrorFrame(Frame):
        def __init__(self, error="", **kwargs):
            self.error = error

    class InterimTranscriptionFrame(Frame):
        def __init__(self, text="", **kwargs):
            self.text = text

    class TranscriptionFrame(Frame):
        def __init__(self, text="", **kwargs):
            self.text = text

    class TTSAudioRawFrame(Frame):
        def __init__(self, audio=b"", sample_rate=16000, num_channels=1, **kwargs):
            self.audio = audio
            self.sample_rate = sample_rate
            self.num_channels = num_channels

    for cls in (Frame, ErrorFrame, InterimTranscriptionFrame, TranscriptionFrame, TTSAudioRawFrame):
        setattr(frames_frames_mod, cls.__name__, cls)

    frames_mod.frames = frames_frames_mod
    mock_pipecat.frames = frames_mod

    transcriptions_mod = types.ModuleType("pipecat.transcriptions")
    lang_mod = types.ModuleType("pipecat.transcriptions.language")

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

    lang_mod.Language = Language
    transcriptions_mod.language = lang_mod
    mock_pipecat.transcriptions = transcriptions_mod

    sys.modules["pipecat"] = mock_pipecat
    sys.modules["pipecat.frames"] = frames_mod
    sys.modules["pipecat.frames.frames"] = frames_frames_mod
    sys.modules["pipecat.transcriptions"] = transcriptions_mod
    sys.modules["pipecat.transcriptions.language"] = lang_mod

from app.main import app
from app.services.session_store import get_session_store


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def clean_session_store():
    """Ensure in-memory session store is cleared before each test."""
    store = get_session_store()
    store.clear()
    yield
    store.clear()


@pytest.fixture
def client():
    """FastAPI TestClient fixture."""
    return TestClient(app)
