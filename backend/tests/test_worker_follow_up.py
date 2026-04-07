import os
import sys
import unittest
import asyncio
from unittest.mock import patch

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import worker_follow_up
from models import PodcastFeedEntry


class MockDatabase:
    def __init__(self):
        self.items = {}
        self.feed_entries = {}
        self.worker_jobs = []

    async def get_shared_item(self, item_id):
        return self.items.get(item_id)

    async def get_follow_up_notes(self, item_id):
        return [{"text": "Please add this to my podcast feed", "note_type": "follow_up"}]

    async def update_shared_item(self, item_id, updates):
        if item_id in self.items:
            self.items[item_id].update(updates)
            return True
        return False

    async def delete_shared_item(self, item_id, user_email):
        self.items.pop(item_id, None)
        return True

    async def get_podcast_feed_entry_by_item(self, user_email, item_id):
        return self.feed_entries.get((user_email, item_id))

    async def create_podcast_feed_entry(self, entry: PodcastFeedEntry):
        self.feed_entries[(entry.user_email, entry.item_id)] = {
            "firestore_id": entry.id,
            "user_email": entry.user_email,
            "item_id": entry.item_id,
            "status": entry.status,
            "title": entry.title,
        }
        return entry

    async def update_podcast_feed_entry(self, entry_id, updates):
        for key, value in list(self.feed_entries.items()):
            if value.get("firestore_id") == entry_id:
                value.update(updates)
                return True
        return False

    async def enqueue_worker_job(self, item_id, user_email, job_type, payload=None):
        self.worker_jobs.append({
            "item_id": item_id,
            "user_email": user_email,
            "job_type": job_type,
            "payload": payload or {},
        })
        return str(len(self.worker_jobs))


class TestWorkerFollowUp(unittest.TestCase):
    @patch("worker_follow_up.send_irccat_message")
    @patch("worker_follow_up.analyze_follow_up")
    def test_follow_up_update_enqueues_podcast_job_when_requested(self, mock_analyze_follow_up, mock_send_irccat):
        mock_db = MockDatabase()
        item_id = "item-follow-up-1"
        mock_db.items[item_id] = {
            "firestore_id": item_id,
            "user_email": "dev@example.com",
            "title": "Original item",
            "type": "text",
            "content": "Some content",
            "status": "follow_up",
            "analysis": {
                "overview": "Original overview",
                "follow_up": "What should I do with this?"
            },
        }

        mock_analyze_follow_up.return_value = {
            "action": "update",
            "reasoning": "User asked for podcast inclusion",
            "analysis": {
                "overview": "Updated overview",
                "podcast_candidate": True,
                "podcast_source_kind": "narration",
                "podcast_title": "Podcast episode",
                "podcast_summary": "Episode summary",
            },
        }

        success, error = asyncio.run(
            worker_follow_up._process_follow_up_item(
                mock_db,
                mock_db.items[item_id],
                {"tags_by_user": {}},
            )
        )

        self.assertTrue(success)
        self.assertIsNone(error)
        self.assertEqual(mock_db.items[item_id]["status"], "analyzed")
        self.assertTrue(mock_db.items[item_id]["analysis"]["podcast_candidate"])
        self.assertEqual([job["job_type"] for job in mock_db.worker_jobs], ["podcast_audio"])
        self.assertEqual(mock_db.feed_entries[("dev@example.com", item_id)]["title"], "Podcast episode")


if __name__ == "__main__":
    unittest.main()
