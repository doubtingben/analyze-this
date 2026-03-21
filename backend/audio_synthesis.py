import os
import logging
from abc import ABC, abstractmethod

import requests

logger = logging.getLogger(__name__)


class AudioSynthesisProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str) -> bytes:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def model(self) -> str:
        pass


class ElevenLabsSynthesisProvider(AudioSynthesisProvider):
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL")
        self._model = os.getenv("TTS_MODEL", "eleven_multilingual_v2")

    @property
    def name(self) -> str:
        return "elevenlabs"

    @property
    def model(self) -> str:
        return self._model

    def synthesize(self, text: str) -> bytes:
        if not self.api_key:
            raise RuntimeError("ELEVENLABS_API_KEY is required for ElevenLabs TTS")

        if not text or not text.strip():
            raise ValueError("Cannot synthesize empty text")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}"
        response = requests.post(
            url,
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": self._model,
                "voice_settings": {
                    "stability": 0.4,
                    "similarity_boost": 0.75,
                },
            },
            timeout=90,
        )
        response.raise_for_status()
        return response.content


class DummySynthesisProvider(AudioSynthesisProvider):
    """Development fallback provider used when no remote provider is configured."""

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def model(self) -> str:
        return os.getenv("TTS_MODEL", "dummy")

    def synthesize(self, text: str) -> bytes:
        # Not valid MP3, but allows local pipeline testing when provider creds are unavailable.
        return text.encode("utf-8")


def get_tts_provider() -> AudioSynthesisProvider:
    provider_name = os.getenv("TTS_PROVIDER", "elevenlabs").strip().lower()

    if provider_name == "elevenlabs":
        return ElevenLabsSynthesisProvider()

    logger.warning("Unknown TTS_PROVIDER=%s, falling back to dummy provider", provider_name)
    return DummySynthesisProvider()
