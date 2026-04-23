import os
import base64

import httpx

from podcast_content import concatenate_mp3_segments, read_blob_bytes
from podcast_drivers.base import AudioGenerationResult, PodcastAudioDriver


class ElevenLabsPodcastAudioDriver(PodcastAudioDriver):
    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID")
        self.model_id = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
        self.output_format = os.getenv("ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_192")
        self.voice_settings = {
            "stability": float(os.getenv("ELEVENLABS_VOICE_STABILITY", "0.55")),
            "similarity_boost": float(os.getenv("ELEVENLABS_VOICE_SIMILARITY_BOOST", "0.75")),
            "style": float(os.getenv("ELEVENLABS_VOICE_STYLE", "0.1")),
            "use_speaker_boost": os.getenv("ELEVENLABS_USE_SPEAKER_BOOST", "true").lower() not in {"0", "false", "no"},
            "speed": float(os.getenv("ELEVENLABS_VOICE_SPEED", "1.05")),
        }
        self.max_chunk_chars = int(os.getenv("PODCAST_TTS_MAX_CHARS", "2200"))

    async def synthesize_speech(self, *, text: str, title: str | None, voice_id: str | None, metadata: dict | None) -> AudioGenerationResult:
        if not self.api_key:
            raise RuntimeError("missing_elevenlabs_api_key")

        chosen_voice_id = voice_id or self.voice_id
        if not chosen_voice_id:
            raise RuntimeError("missing_elevenlabs_voice_id")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{chosen_voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            segments = []
            chunk_count = 0
            for chunk_count, chunk_text in enumerate(self._chunk_text(text), start=1):
                payload = {
                    "text": chunk_text,
                    "model_id": self.model_id,
                    "voice_settings": self.voice_settings,
                    "output_format": self.output_format,
                }
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                segments.append(response.content)

            if not segments:
                raise RuntimeError("missing_tts_audio")

            combined_audio = concatenate_mp3_segments(segments)
            return AudioGenerationResult(
                audio_bytes=combined_audio,
                mime_type="audio/mpeg",
                provider="elevenlabs",
                provider_metadata={
                    "title": title,
                    "chunk_count": chunk_count,
                    "voice_id": chosen_voice_id,
                    "voice_settings": self.voice_settings,
                    **(metadata or {}),
                },
            )

    async def normalize_source_audio(self, *, source_item: dict, metadata: dict | None) -> AudioGenerationResult:
        source_path = source_item.get("content")
        if not source_path:
            raise RuntimeError("missing_source_audio")

        mime_type = ((source_item.get("item_metadata") or {}).get("mimeType") or "audio/mpeg").lower()
        audio_bytes = await self._read_source_audio_bytes(source_path)
        return AudioGenerationResult(
            audio_bytes=audio_bytes,
            mime_type=mime_type,
            provider="source",
            provider_metadata=metadata or {},
        )

    async def _read_source_audio_bytes(self, source_path: str) -> bytes:
        if source_path.startswith(("http://", "https://")):
            async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
                response = await client.get(source_path)
                response.raise_for_status()
                return response.content

        if source_path.startswith("data:"):
            try:
                _, encoded = source_path.split(",", 1)
            except ValueError as exc:
                raise RuntimeError("invalid_data_url") from exc
            return base64.b64decode(encoded)

        return read_blob_bytes(source_path)

    def _chunk_text(self, text: str) -> list[str]:
        cleaned_text = (text or "").strip()
        if not cleaned_text:
            return []

        chunks = []
        current_parts = []
        current_length = 0
        paragraphs = [paragraph.strip() for paragraph in cleaned_text.split("\n\n") if paragraph.strip()]
        for paragraph in paragraphs:
            paragraph_length = len(paragraph) + (2 if current_parts else 0)
            if current_parts and current_length + paragraph_length > self.max_chunk_chars:
                chunks.append("\n\n".join(current_parts))
                current_parts = [paragraph]
                current_length = len(paragraph)
                continue

            if len(paragraph) > self.max_chunk_chars:
                if current_parts:
                    chunks.append("\n\n".join(current_parts))
                    current_parts = []
                    current_length = 0
                chunks.extend(self._split_long_paragraph(paragraph))
                continue

            current_parts.append(paragraph)
            current_length += paragraph_length

        if current_parts:
            chunks.append("\n\n".join(current_parts))
        return chunks

    def _split_long_paragraph(self, paragraph: str) -> list[str]:
        words = paragraph.split()
        chunks = []
        current_words = []
        current_length = 0
        for word in words:
            next_length = current_length + len(word) + (1 if current_words else 0)
            if current_words and next_length > self.max_chunk_chars:
                chunks.append(" ".join(current_words))
                current_words = [word]
                current_length = len(word)
                continue
            current_words.append(word)
            current_length = next_length
        if current_words:
            chunks.append(" ".join(current_words))
        return chunks
