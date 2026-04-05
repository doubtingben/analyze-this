from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AudioGenerationResult:
    audio_bytes: Optional[bytes] = None
    mime_type: str = "audio/mpeg"
    duration_seconds: Optional[int] = None
    provider: Optional[str] = None
    provider_job_id: Optional[str] = None
    provider_metadata: dict = field(default_factory=dict)


class PodcastAudioDriver(ABC):
    @abstractmethod
    async def synthesize_speech(self, *, text: str, title: str | None, voice_id: str | None, metadata: dict | None) -> AudioGenerationResult:
        raise NotImplementedError

    @abstractmethod
    async def normalize_source_audio(self, *, source_item: dict, metadata: dict | None) -> AudioGenerationResult:
        raise NotImplementedError
