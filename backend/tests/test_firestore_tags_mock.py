import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import asyncio

# Ensure we can import from backend
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock firebase_admin before importing database
with patch('firebase_admin.initialize_app'), patch('firebase_admin.credentials'):
    from database import FirestoreDatabase

class TestFirestoreTagsOptimization(unittest.TestCase):
    def setUp(self):
        self.mock_db_client = MagicMock()
        with patch('database.firestore.client', return_value=self.mock_db_client):
            self.db = FirestoreDatabase()

    def test_get_user_tags_cached(self):
        """Test that get_user_tags uses cache if available."""
        user_email = "test@example.com"

        # Mock user_tags doc existence
        mock_doc = MagicMock()
        mock_doc.exists = True
        # Base64 for "tag1" is "dGFnMQ"
        # Base64 for "tag2" is "dGFnMg"
        mock_doc.to_dict.return_value = {
            "tags": {
                "dGFnMQ": 1, # tag1
                "dGFnMg": 2  # tag2
            }
        }

        mock_user_tags_ref = MagicMock()
        mock_user_tags_ref.get.return_value = mock_doc

        # Setup collection mock
        def collection_side_effect(name):
            if name == 'user_tags':
                col = MagicMock()
                col.document.return_value = mock_user_tags_ref
                return col
            if name == 'shared_items':
                return MagicMock() # Should not be used for query if cached
            return MagicMock()

        self.mock_db_client.collection.side_effect = collection_side_effect

        # Run
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tags = loop.run_until_complete(self.db.get_user_tags(user_email))
        loop.close()

        # Verify
        self.assertEqual(tags, ["tag1", "tag2"])

        # Verify user_tags collection was accessed
        self.mock_db_client.collection.assert_any_call('user_tags')

        # Verify shared_items was NOT queried (no stream)
        # We can check if 'shared_items' collection was accessed.
        # But get_user_tags calls collection('shared_items') inside fallback?
        # No, fallback code is only reached if doc.exists is False.
        # But wait, collection('shared_items') is not called if doc.exists is True?
        # Let's check the code structure.
        # It's inside `get_tags` function.
        # If doc.exists: return ...
        # So fallback lines are not executed.

        # So `self.mock_db_client.collection('shared_items')` should NOT be called?
        # Actually `self.mock_db_client.collection` is a mock.
        # It IS called with 'user_tags'.
        # We can check calls.

        calls = [c[0][0] for c in self.mock_db_client.collection.call_args_list]
        self.assertNotIn('shared_items', calls)

    def test_get_user_tags_backfill(self):
        """Test that get_user_tags falls back to O(N) scan and backfills if cache missing."""
        user_email = "test@example.com"

        # Mock user_tags doc MISSING
        mock_doc = MagicMock()
        mock_doc.exists = False

        mock_user_tags_ref = MagicMock()
        mock_user_tags_ref.get.return_value = mock_doc

        # Mock shared_items query
        mock_items_ref = MagicMock()
        mock_query = MagicMock()
        mock_items_ref.where.return_value = mock_query

        # Mock stream results
        item1 = MagicMock()
        item1.to_dict.return_value = {"analysis": {"tags": ["tagA"]}}
        item2 = MagicMock()
        item2.to_dict.return_value = {"analysis": {"tags": ["tagB", "tagA"]}}

        mock_query.stream.return_value = [item1, item2]

        def collection_side_effect(name):
            if name == 'user_tags':
                col = MagicMock()
                col.document.return_value = mock_user_tags_ref
                return col
            if name == 'shared_items':
                return mock_items_ref
            return MagicMock()

        self.mock_db_client.collection.side_effect = collection_side_effect

        # Run
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tags = loop.run_until_complete(self.db.get_user_tags(user_email))
        loop.close()

        # Verify
        self.assertEqual(sorted(tags), ["tagA", "tagB"])

        # Verify backfill write
        # tagA count: 2
        # tagB count: 1
        # Expect set call on user_tags_ref
        mock_user_tags_ref.set.assert_called_once()
        args, kwargs = mock_user_tags_ref.set.call_args

        updates = args[0]
        self.assertTrue(kwargs.get('merge'))

        # Check encoded keys
        # tagA -> dGFnQQ
        # tagB -> dGFnQg
        self.assertEqual(updates.get("tags.dGFnQQ"), 2)
        self.assertEqual(updates.get("tags.dGFnQg"), 1)

if __name__ == "__main__":
    unittest.main()
