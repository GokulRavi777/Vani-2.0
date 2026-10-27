"""Custom Voice Persistence Store.

Stores and manages enrolled cloned voices and their Gnani speaker embeddings.
Provides thread-safe in-memory caching backed by atomic JSON disk storage.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("custom_voice_store")

DEFAULT_STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage"
DEFAULT_STORAGE_FILE = DEFAULT_STORAGE_DIR / "custom_voices.json"


class CustomVoiceStore:
    """Thread-safe persistent store for custom voice embeddings."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or DEFAULT_STORAGE_FILE
        self._lock = threading.Lock()
        self._voices: Dict[str, Dict[str, Any]] = {}
        self._ensure_storage_dir()
        self._load()

    def _ensure_storage_dir(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.warning("Could not create storage directory %s: %s", self.storage_path.parent, e)

    def _load(self) -> None:
        """Load stored voices from disk into memory."""
        if not self.storage_path.exists():
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self._voices = data
                logger.info("Loaded %d custom voice(s) from %s", len(self._voices), self.storage_path)
        except Exception as e:
            logger.error("Failed to load custom voices from %s: %s", self.storage_path, e)
            self._voices = {}

    def _save(self) -> None:
        """Atomically persist voices to disk."""
        try:
            self._ensure_storage_dir()
            tmp_path = self.storage_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self._voices, f, indent=2)
            # Atomic replace
            os.replace(tmp_path, self.storage_path)
        except Exception as e:
            logger.error("Failed to save custom voices to %s: %s", self.storage_path, e)

    def save_voice(
        self,
        voice_id: str,
        name: str,
        speaker_embedding: Dict[str, Any],
        language: str = "en-IN",
        gender: str = "Custom",
        description: str = "Custom voice cloned via Gnani AI",
        duration_sec: Optional[float] = None
    ) -> Dict[str, Any]:
        """Save or update an enrolled custom voice."""
        record = {
            "voice_id": voice_id,
            "name": name,
            "language": language,
            "gender": gender,
            "description": description,
            "speaker_embedding": speaker_embedding,
            "duration_sec": duration_sec,
            "status": "active"
        }
        with self._lock:
            self._voices[voice_id] = record
            self._save()
        logger.info("Enrolled custom voice '%s' (%s) securely.", name, voice_id)
        return record

    def get_voice(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve custom voice by ID."""
        with self._lock:
            voice = self._voices.get(voice_id)
            if voice:
                return dict(voice)
            return None

    def list_voices(self) -> List[Dict[str, Any]]:
        """List all enrolled custom voices (without raw heavy embeddings)."""
        with self._lock:
            result = []
            for v_id, v in self._voices.items():
                result.append({
                    "id": v_id,
                    "name": v.get("name", v_id),
                    "language": v.get("language", "en-IN"),
                    "gender": v.get("gender", "Custom"),
                    "persona": "Cloned Voice",
                    "description": v.get("description", "Custom voice cloned via Gnani AI"),
                    "is_custom": True,
                    "status": v.get("status", "active")
                })
            return result

    def delete_voice(self, voice_id: str) -> bool:
        """Delete an enrolled custom voice."""
        with self._lock:
            if voice_id in self._voices:
                del self._voices[voice_id]
                self._save()
                logger.info("Deleted custom voice %s", voice_id)
                return True
            return False

    def clear(self) -> None:
        """Clear all stored custom voices (used in testing)."""
        with self._lock:
            self._voices.clear()
            self._save()


# Singleton instance
_custom_voice_store = CustomVoiceStore()


def get_custom_voice_store() -> CustomVoiceStore:
    return _custom_voice_store
