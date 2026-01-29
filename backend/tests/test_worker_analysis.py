import os
import sys
import unittest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

# Add backend directory to path
sys.path.append(os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

import worker_analysis

# Mock Database Interface
class MockDatabase:
    def __init__(self):
        self.items = {}
        
    async def get_shared_item(self, item_id):
        return self.items.get(item_id)
        
    async def get_items_by_status(self, status, limit=10):
        return [item for item in self.items.values() if item.get('status') == status][:limit]
        
    async def update_shared_item(self, item_id, updates):
        if item_id in self.items:
            self.items[item_id].update(updates)
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
            "timeline": {"date": "2023-10-27", "principal": "Test"}
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
        self.assertEqual(updated_item['analysis'], {"overview": "Forced Analysis", "timeline": {"date": "2024-01-01"}})

if __name__ == "__main__":
    unittest.main()
