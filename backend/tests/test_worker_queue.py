import unittest
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock, patch
import logging

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from worker_queue import process_queue_jobs

# Mock logger
logger = logging.getLogger("test_worker_queue")

class TestWorkerQueue(unittest.TestCase):
    @patch('worker_queue.init_tracing')
    @patch('worker_queue.shutdown_tracing')
    @patch('worker_queue.create_span')
    @patch('worker_queue.create_linked_span')
    def test_process_queue_jobs_batch_fetch(self, mock_linked_span, mock_span, mock_shutdown, mock_init):
        # Setup mocks
        mock_db = MagicMock()
        mock_db.lease_worker_jobs = AsyncMock()
        mock_db.get_shared_items_by_ids = AsyncMock()
        mock_db.get_shared_item = AsyncMock()
        mock_db.complete_worker_job = AsyncMock()
        mock_db.fail_worker_job = AsyncMock()

        async def get_db():
            return mock_db

        # Mock create_span context manager
        mock_span_ctx = MagicMock()
        mock_span.return_value.__enter__.return_value = mock_span_ctx

        mock_linked_span_ctx = MagicMock()
        mock_linked_span.return_value.__enter__.return_value = mock_linked_span_ctx

        # Jobs data
        jobs = [
            {'firestore_id': 'job1', 'item_id': 'item1', 'user_email': 'user1'},
            {'firestore_id': 'job2', 'item_id': 'item2', 'user_email': 'user2'},
            {'firestore_id': 'job3', 'item_id': 'item1', 'user_email': 'user1'}, # Duplicate item
        ]
        mock_db.lease_worker_jobs.return_value = jobs

        # Items data to be returned by batch fetch
        items = [
            {'firestore_id': 'item1', 'title': 'Item 1'},
            {'firestore_id': 'item2', 'title': 'Item 2'},
        ]
        mock_db.get_shared_items_by_ids.return_value = items

        # Process function
        process_fn = AsyncMock(return_value=(True, None))

        # Run
        asyncio.run(process_queue_jobs(
            job_type="test",
            limit=10,
            lease_seconds=60,
            get_db=get_db,
            process_item_fn=process_fn,
            logger=logger,
            continuous=False
        ))

        # Verify
        # 1. Check if get_shared_items_by_ids was called with unique item IDs
        mock_db.get_shared_items_by_ids.assert_called_once()
        called_args = mock_db.get_shared_items_by_ids.call_args[0][0]
        self.assertEqual(set(called_args), {'item1', 'item2'})

        # 2. Check if get_shared_item (individual fetch) was NOT called
        mock_db.get_shared_item.assert_not_called()

        # 3. Check if process_fn was called for each job
        self.assertEqual(process_fn.call_count, 3)

        # Verify arguments passed to process_fn
        # Items might be processed in any order if concurrent, but here it's sequential loop
        # Job 1 -> Item 1
        args, _ = process_fn.call_args_list[0]
        self.assertEqual(args[1]['firestore_id'], 'item1')

        # Job 2 -> Item 2
        args, _ = process_fn.call_args_list[1]
        self.assertEqual(args[1]['firestore_id'], 'item2')

        # Job 3 -> Item 1
        args, _ = process_fn.call_args_list[2]
        self.assertEqual(args[1]['firestore_id'], 'item1')

    @patch('worker_queue.init_tracing')
    @patch('worker_queue.shutdown_tracing')
    @patch('worker_queue.create_span')
    @patch('worker_queue.create_linked_span')
    def test_process_queue_jobs_fallback(self, mock_linked_span, mock_span, mock_shutdown, mock_init):
        # Test fallback when batch fetch misses an item
        mock_db = MagicMock()
        mock_db.lease_worker_jobs = AsyncMock()
        mock_db.get_shared_items_by_ids = AsyncMock()
        mock_db.get_shared_item = AsyncMock()
        mock_db.complete_worker_job = AsyncMock()

        async def get_db():
            return mock_db

        mock_span.return_value.__enter__.return_value = MagicMock()
        mock_linked_span.return_value.__enter__.return_value = MagicMock()

        jobs = [{'firestore_id': 'job1', 'item_id': 'item1'}]
        mock_db.lease_worker_jobs.return_value = jobs

        # Batch fetch returns empty (simulating failure or missing item)
        mock_db.get_shared_items_by_ids.return_value = []

        # Individual fetch returns the item
        mock_db.get_shared_item.return_value = {'firestore_id': 'item1', 'title': 'Item 1'}

        process_fn = AsyncMock(return_value=(True, None))

        asyncio.run(process_queue_jobs(
            job_type="test",
            limit=10,
            lease_seconds=60,
            get_db=get_db,
            process_item_fn=process_fn,
            logger=logger,
            continuous=False
        ))

        # Verify
        mock_db.get_shared_items_by_ids.assert_called_once()
        mock_db.get_shared_item.assert_called_once_with('item1')
        process_fn.assert_called_once()

if __name__ == '__main__':
    unittest.main()
