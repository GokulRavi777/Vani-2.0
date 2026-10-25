"""Speech-to-Text (STT) Provider Interface & Adapters Skeleton.

Defines the contract for streaming or chunk-based transcription evaluation.
In Stages 3 and 4:
- Google STT adapter will implement streaming linear16 transcription via Google Speech-to-Text.
- Sarvam STT adapter will implement Sarvam AI Saaras v4 transcription with keyterm prompting.
- Compare mode will orchestrate dual evaluation across both providers.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional
from app.schemas.assessment import STTMode


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
    """Stub adapter for Google Cloud Speech-to-Text (Stage 3)."""
    @property
    def provider_name(self) -> str:
        return "google"

    def is_configured(self) -> bool:
        return False

    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language_code: str = "en-IN",
        keywords: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, object], None]:
        raise NotImplementedError("Google STT adapter will be implemented in Stage 3.")


class SarvamSTTAdapter(STTProviderInterface):
    """Stub adapter for Sarvam AI Saaras v4 STT (Stage 3)."""
    @property
    def provider_name(self) -> str:
        return "sarvam"

    def is_configured(self) -> bool:
        return False

    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language_code: str = "en-IN",
        keywords: Optional[List[str]] = None
    ) -> AsyncGenerator[Dict[str, object], None]:
        raise NotImplementedError("Sarvam STT adapter will be implemented in Stage 3.")


class STTBenchmarkOrchestrator:
    """Orchestrator for managing provider selection and comparative evaluation (Stage 4)."""

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
