import os
import sys
import unittest
from unittest.mock import patch

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import worker_analysis


class FakeDoc:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    def to_dict(self):
        return self._data

    @property
    def exists(self):
        return True


class FakeDocRef:
    def __init__(self, doc):
        self._doc = doc
        self.updated = None

    def get(self):
        return self._doc

    def update(self, payload):
        self.updated = payload


class FakeQuery:
    def __init__(self, docs):
        self._docs = docs

    def limit(self, _limit):
        return self

    def stream(self):
        return list(self._docs)


class FakeCollection:
    def __init__(self, docs_by_id, docs):
        self._docs_by_id = docs_by_id
        self._docs = docs
        self._doc_refs = {}

    def document(self, doc_id):
        if doc_id not in self._doc_refs:
            self._doc_refs[doc_id] = FakeDocRef(self._docs_by_id[doc_id])
        return self._doc_refs[doc_id]

    def where(self, field_path=None, op_string=None, value=None):
        return FakeQuery(self._docs)


class FakeFirestore:
    def __init__(self, docs_by_id, docs):
        self._docs_by_id = docs_by_id
        self._docs = docs
        self.collection_called = None
        self._collection = FakeCollection(self._docs_by_id, self._docs)

    def collection(self, name):
        self.collection_called = name
        return self._collection


class TestWorkerAnalysis(unittest.TestCase):
    def test_process_items_updates_unanalyzed(self):
        doc = FakeDoc("item-1", {"content": "hello", "type": "text", "analysis": None})
        firestore_client = FakeFirestore({"item-1": doc}, [doc])

        with patch("worker_analysis.firestore.client", return_value=firestore_client), patch(
            "worker_analysis.analyze_content", return_value={"step": "add_event"}
        ):
            worker_analysis.process_items(limit=1)

        doc_ref = firestore_client.collection("shared_items").document("item-1")
        self.assertEqual(doc_ref.updated, {"analysis": {"step": "add_event"}})

    def test_process_items_skips_missing_content(self):
        doc = FakeDoc("item-2", {"content": None, "type": "text", "analysis": None})
        firestore_client = FakeFirestore({"item-2": doc}, [doc])

        with patch("worker_analysis.firestore.client", return_value=firestore_client), patch(
            "worker_analysis.analyze_content"
        ) as mock_analyze:
            worker_analysis.process_items(limit=1)

        mock_analyze.assert_not_called()
        doc_ref = firestore_client.collection("shared_items").document("item-2")
        self.assertIsNone(doc_ref.updated)

    def test_process_items_specific_id(self):
        doc = FakeDoc("item-3", {"content": "hello", "type": "text", "analysis": None})
        firestore_client = FakeFirestore({"item-3": doc}, [])

        with patch("worker_analysis.firestore.client", return_value=firestore_client), patch(
            "worker_analysis.analyze_content", return_value={"step": "add_event"}
        ):
            worker_analysis.process_items(item_id="item-3", force=True)

        doc_ref = firestore_client.collection("shared_items").document("item-3")
        self.assertEqual(doc_ref.updated, {"analysis": {"step": "add_event"}})


if __name__ == "__main__":
    unittest.main()
