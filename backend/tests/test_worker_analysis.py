import os
import sys
import unittest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import worker_analysis
from models import PodcastFeedEntry

# Mock Database Interface
class MockDatabase:
    def __init__(self):
        self.items = {}
        self.worker_jobs = []
        self.feed_entries = {}
        
    async def get_shared_item(self, item_id):
        return self.items.get(item_id)
        
    async def get_items_by_status(self, status, limit=10):
        return [item for item in self.items.values() if item.get('status') == status][:limit]
        
    async def update_shared_item(self, item_id, updates):
        if item_id in self.items:
            self.items[item_id].update(updates)
            return True
        return False

    async def get_user_tags(self, user_email):
        return []

    async def enqueue_worker_job(self, item_id, user_email, job_type, payload=None):
        self.worker_jobs.append({
            "item_id": item_id,
            "user_email": user_email,
            "job_type": job_type,
            "payload": payload or {},
        })
        return str(len(self.worker_jobs))

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

class TestWorkerAnalysis(unittest.TestCase):
    def setUp(self):
        self.mock_db = MockDatabase()
        
    @patch('worker_analysis.get_db', new_callable=AsyncMock)
    @patch('worker_analysis.analyze_content')
    def test_process_items_async_success(self, mock_analyze, mock_get_db):
        # Setup
        mock_get_db.return_value = self.mock_db
        # Updated to match new model: timeline object instead of action string
        mock_analyze.return_value = {
            "overview": "Analysis Done",
            "timeline": {"date": "2023-10-27", "principal": "Test"}
        }
        
        # Data
        item_id = "item-1"
        self.mock_db.items[item_id] = {
            "firestore_id": item_id,
            "content": "hello", 
            "type": "text", 
            "status": "new"
        }
        
        # Execute
        asyncio.run(worker_analysis.process_items_async(limit=1))
        
        # Verify
        updated_item = self.mock_db.items[item_id]
        # worker_analysis sets status based on presence of timeline key
        self.assertEqual(updated_item['status'], 'timeline')
        self.assertEqual(updated_item['analysis'], {
            "overview": "Analysis Done",
            "timeline": {"date": "2023-10-27", "principal": "Test"},
            "podcast_candidate": True,
            "podcast_candidate_reason": None,
            "podcast_source_kind": "narration",
            "podcast_title": None,
            "podcast_summary": "Analysis Done",
        })
        self.assertEqual(updated_item['next_step'], 'timeline')
        
    @patch('worker_analysis.get_db', new_callable=AsyncMock)
    @patch('worker_analysis.analyze_content')
    def test_process_items_async_skips_no_content(self, mock_analyze, mock_get_db):
        # Setup
        mock_get_db.return_value = self.mock_db
        
        # Data
        item_id = "item-2"
        self.mock_db.items[item_id] = {
            "firestore_id": item_id,
            "content": None, 
            "type": "text", 
            "status": "new"
        }
        
        # Execute
        asyncio.run(worker_analysis.process_items_async(limit=1))
        
        # Verify
        updated_item = self.mock_db.items[item_id]
        self.assertEqual(updated_item['status'], 'processed')  # Should be processed/skipped
        self.assertEqual(updated_item['next_step'], 'no_content')
        mock_analyze.assert_not_called()

    @patch('worker_analysis.get_db', new_callable=AsyncMock)
    @patch('worker_analysis.analyze_content')
    def test_process_items_async_specific_id(self, mock_analyze, mock_get_db):
        # Setup
        mock_get_db.return_value = self.mock_db
        mock_analyze.return_value = {"overview": "Forced Analysis", "timeline": {"date": "2024-01-01"}}
        
        # Data
        item_id = "item-3"
        self.mock_db.items[item_id] = {
            "firestore_id": item_id,
            "content": "force me", 
            "type": "text", 
            "status": "analyzed",
            "analysis": {"old": "analysis"}
        }
        
        # Execute with force=True
        asyncio.run(worker_analysis.process_items_async(item_id=item_id, force=True))
        
        # Verify
        updated_item = self.mock_db.items[item_id]
        self.assertEqual(updated_item['analysis']["overview"], "Forced Analysis")
        self.assertEqual(updated_item['analysis']["timeline"], {"date": "2024-01-01"})

    @patch('worker_analysis.analyze_content')
    def test_process_analysis_item_enqueues_podcast_job(self, mock_analyze):
        mock_analyze.return_value = {
            "overview": "Podcast ready text",
            "podcast_candidate": True,
            "podcast_source_kind": "narration",
            "podcast_title": "Episode title",
            "podcast_summary": "Episode summary",
        }

        item_id = "item-4"
        self.mock_db.items[item_id] = {
            "firestore_id": item_id,
            "content": "podcast me",
            "type": "text",
            "status": "new",
            "user_email": "dev@example.com",
            "title": "My item",
        }

        asyncio.run(worker_analysis._process_analysis_item(self.mock_db, self.mock_db.items[item_id], {"tags_by_user": {}}))

        self.assertEqual(
            [job["job_type"] for job in self.mock_db.worker_jobs],
            ["normalize", "podcast_audio"]
        )
        feed_entry = self.mock_db.feed_entries[("dev@example.com", item_id)]
        self.assertEqual(feed_entry["status"], "queued")
        self.assertEqual(feed_entry["title"], "Episode title")

if __name__ == "__main__":
    unittest.main()
