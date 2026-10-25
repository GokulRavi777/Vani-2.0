"""Text-to-Speech (TTS) Provider Interface.

Defines the contract for synthesizing question audio for the candidate.
Concrete implementations (e.g., Google Cloud Text-to-Speech) will be integrated
in Stage 2 without altering the assessment generation workflow.
"""

from abc import ABC, abstractmethod
from typing import Optional


class TTSProviderInterface(ABC):
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        language_code: str = "en-IN",
        voice_name: Optional[str] = None
    ) -> bytes:
        """Synthesize question text into audio bytes (e.g., MP3/WAV)."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if provider credentials and client are available."""
        pass
