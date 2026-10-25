"""Session Store Service.

Provides an isolated in-memory session repository for prototype assessments.
NOTE: In-memory sessions are temporary and will not survive backend restarts.
The interface is structured so that a persistent database (e.g. Postgres or Redis)
can replace this implementation in future stages with zero router modifications.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import threading

from app.schemas.assessment import AssessmentResponse


class SessionStoreInterface(ABC):
    @abstractmethod
    def save(self, assessment: AssessmentResponse) -> None:
        """Save or update an assessment session."""
        pass

    @abstractmethod
    def get(self, assessment_id: str) -> Optional[AssessmentResponse]:
        """Retrieve an assessment session by its unique ID. Returns None if not found."""
        pass

    @abstractmethod
    def exists(self, assessment_id: str) -> bool:
        """Check if an assessment session exists."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored sessions (useful for test resets)."""
        pass


class InMemorySessionStore(SessionStoreInterface):
    """Thread-safe in-memory session store."""

    def __init__(self) -> None:
        self._storage: Dict[str, AssessmentResponse] = {}
        self._lock = threading.Lock()

    def save(self, assessment: AssessmentResponse) -> None:
        with self._lock:
            # Save a copy to prevent in-place mutation side-effects
            self._storage[assessment.assessment_id] = assessment.model_copy(deep=True)

    def get(self, assessment_id: str) -> Optional[AssessmentResponse]:
        with self._lock:
            found = self._storage.get(assessment_id)
            if found:
                return found.model_copy(deep=True)
            return None

    def exists(self, assessment_id: str) -> bool:
        with self._lock:
            return assessment_id in self._storage

    def clear(self) -> None:
        with self._lock:
            self._storage.clear()


# Global singleton instance for prototype lifecycle
_default_session_store = InMemorySessionStore()


def get_session_store() -> SessionStoreInterface:
    """FastAPI dependency provider for session storage."""
    return _default_session_store
