import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from podcast_drivers.base import AudioGenerationResult
from worker_podcast_audio import _process_podcast_audio_item


class _MockPodcastDb:
    def __init__(self):
        self.feed_entry = {
            "firestore_id": "feed-1",
            "status": "queued",
            "source_kind": "narration",
            "title": "Existing feed title",
        }
        self.updates = []

    async def get_podcast_feed_entry_by_item(self, user_email, item_id):
        return self.feed_entry

    async def update_podcast_feed_entry(self, entry_id, updates):
        self.updates.append((entry_id, updates))
        self.feed_entry.update(updates)
        return True


class _MockPodcastDriver:
    async def synthesize_speech(self, *, text, title, voice_id, metadata):
        return AudioGenerationResult(
            audio_bytes=b"raw-audio",
            mime_type="audio/mpeg",
            duration_seconds=12,
            provider="mock",
        )

    async def normalize_source_audio(self, *, source_item, metadata):
        raise AssertionError("native audio path should not be used")


class _MockNativeAudioDriver:
    async def synthesize_speech(self, *, text, title, voice_id, metadata):
        raise AssertionError("narration path should not be used")

    async def normalize_source_audio(self, *, source_item, metadata):
        return AudioGenerationResult(
            audio_bytes=b"source-audio",
            mime_type="audio/mpeg",
            duration_seconds=9,
            provider="source",
        )


class TestWorkerPodcastAudio(unittest.IsolatedAsyncioTestCase):
    async def test_process_podcast_audio_unwraps_item_analysis_payload(self):
        db = _MockPodcastDb()
        item = {
            "firestore_id": "item-1",
            "user_email": "dev@example.com",
            "type": "text",
            "title": "Item title",
            "content": "Body text for the generated podcast episode.",
            "analysis": {
                "item": {
                    "status": "timeline",
                    "analysis": {
                        "overview": "Wrapped overview",
                        "tags": ["wellness"],
                        "podcast_candidate": True,
                        "podcast_source_kind": "narration",
                        "podcast_title": "Wrapped podcast title",
                        "podcast_summary": "Wrapped podcast summary",
                    },
                }
            },
        }

        with (
            patch("worker_podcast_audio.get_podcast_audio_driver", return_value=_MockPodcastDriver()),
            patch("worker_podcast_audio.normalize_audio_bytes", return_value=(b"normalized-audio", "audio/mpeg")),
            patch("worker_podcast_audio.probe_audio_duration_seconds", return_value=34),
            patch("worker_podcast_audio.upload_audio_bytes", return_value="uploads/dev@example.com/podcast/item-1.mp3"),
        ):
            success, error = await _process_podcast_audio_item(db, item, {})

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(db.feed_entry["status"], "ready")
        self.assertEqual(db.feed_entry["source_kind"], "item_content")
        self.assertIn("Wrapped overview", db.feed_entry["analysis_notes"])
        self.assertIn("wellness", db.feed_entry["analysis_notes"])
        self.assertIn("Wrapped podcast summary", db.feed_entry["script_text"])
        self.assertEqual(db.feed_entry["audio_byte_length"], len(b"normalized-audio"))
        self.assertEqual(db.feed_entry["duration_seconds"], 34)

    async def test_process_native_audio_does_not_set_provider_voice_id(self):
        db = _MockPodcastDb()
        db.feed_entry["source_kind"] = "native_audio"
        item = {
            "firestore_id": "item-audio",
            "user_email": "dev@example.com",
            "type": "audio",
            "title": "Audio item",
            "content": "uploads/dev@example.com/audio.mp3",
            "analysis": {
                "overview": "Audio overview",
                "podcast_source_kind": "native_audio",
            },
        }

        with (
            patch.dict(os.environ, {"ELEVENLABS_VOICE_ID": "voice-should-not-be-used"}, clear=False),
            patch("worker_podcast_audio.get_podcast_audio_driver", return_value=_MockNativeAudioDriver()),
            patch("worker_podcast_audio.normalize_audio_bytes", return_value=(b"normalized-source-audio", "audio/mpeg")),
            patch("worker_podcast_audio.probe_audio_duration_seconds", return_value=None),
            patch("worker_podcast_audio.upload_audio_bytes", return_value="uploads/dev@example.com/podcast/item-audio.mp3"),
        ):
            success, error = await _process_podcast_audio_item(db, item, {})

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(db.feed_entry["provider"], "source")
        self.assertIsNone(db.feed_entry["provider_voice_id"])
        self.assertEqual(db.feed_entry["duration_seconds"], 9)


if __name__ == "__main__":
    unittest.main()
