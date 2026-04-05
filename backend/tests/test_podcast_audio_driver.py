import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from podcast_drivers.elevenlabs import ElevenLabsPodcastAudioDriver


class _MockResponse:
    def __init__(self, content=b"audio-bytes", status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http_{self.status_code}")


class _MockAsyncClient:
    def __init__(self, response):
        self.response = response
        self.posts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, **kwargs):
        return self.response

    async def post(self, url, json=None, headers=None, **kwargs):
        self.posts.append({"url": url, "json": json, "headers": headers})
        return self.response


class TestPodcastAudioDriver(unittest.IsolatedAsyncioTestCase):
    async def test_normalize_source_audio_downloads_external_url(self):
        driver = ElevenLabsPodcastAudioDriver()
        response = _MockResponse(content=b"remote-audio")

        with patch("podcast_drivers.elevenlabs.httpx.AsyncClient", return_value=_MockAsyncClient(response)):
            result = await driver.normalize_source_audio(
                source_item={
                    "content": "https://example.com/audio.mp3",
                    "item_metadata": {"mimeType": "audio/mpeg"},
                },
                metadata={"item_id": "abc"},
            )

        self.assertEqual(result.audio_bytes, b"remote-audio")
        self.assertEqual(result.mime_type, "audio/mpeg")
        self.assertEqual(result.provider, "source")

    async def test_synthesize_speech_uses_voice_settings_and_chunks_long_text(self):
        client = _MockAsyncClient(_MockResponse(content=b"segment-audio"))
        text = "Title\n\nFirst paragraph with enough words to split.\n\nSecond paragraph also needs another chunk."

        with (
            patch.dict(
                os.environ,
                {
                    "ELEVENLABS_API_KEY": "test-key",
                    "ELEVENLABS_VOICE_ID": "voice-123",
                    "PODCAST_TTS_MAX_CHARS": "40",
                },
                clear=False,
            ),
            patch("podcast_drivers.elevenlabs.httpx.AsyncClient", return_value=client),
            patch("podcast_drivers.elevenlabs.concatenate_mp3_segments", return_value=b"combined-audio") as concat_mock,
        ):
            driver = ElevenLabsPodcastAudioDriver()
            result = await driver.synthesize_speech(
                text=text,
                title="Example",
                voice_id=None,
                metadata={"item_id": "abc"},
            )

        self.assertEqual(result.audio_bytes, b"combined-audio")
        self.assertEqual(len(client.posts), 3)
        self.assertEqual(concat_mock.call_count, 1)
        first_payload = client.posts[0]["json"]
        self.assertEqual(first_payload["model_id"], driver.model_id)
        self.assertEqual(first_payload["output_format"], driver.output_format)
        self.assertEqual(first_payload["voice_settings"], driver.voice_settings)
        self.assertEqual(result.provider_metadata["chunk_count"], 3)
        self.assertEqual(result.provider_metadata["item_id"], "abc")


if __name__ == "__main__":
    unittest.main()
