import os

import httpx

from podcast_content import read_blob_bytes
from podcast_drivers.base import AudioGenerationResult, PodcastAudioDriver


class ElevenLabsPodcastAudioDriver(PodcastAudioDriver):
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

    async def synthesize_speech(self, *, text: str, title: str | None, voice_id: str | None, metadata: dict | None) -> AudioGenerationResult:
        if not self.api_key:
            raise RuntimeError("missing_elevenlabs_api_key")

        chosen_voice_id = voice_id or self.voice_id
        if not chosen_voice_id:
            raise RuntimeError("missing_elevenlabs_voice_id")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{chosen_voice_id}"
        payload = {
            "text": text,
            "model_id": self.model_id,
        }
        headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return AudioGenerationResult(
                audio_bytes=response.content,
                mime_type="audio/mpeg",
                provider="elevenlabs",
                provider_metadata={"title": title, **(metadata or {})},
            )

    async def normalize_source_audio(self, *, source_item: dict, metadata: dict | None) -> AudioGenerationResult:
        blob_path = source_item.get("content")
        if not blob_path:
            raise RuntimeError("missing_source_audio")

        mime_type = ((source_item.get("item_metadata") or {}).get("mimeType") or "audio/mpeg").lower()
        return AudioGenerationResult(
            audio_bytes=read_blob_bytes(blob_path),
            mime_type=mime_type,
            provider="source",
            provider_metadata=metadata or {},
        )
