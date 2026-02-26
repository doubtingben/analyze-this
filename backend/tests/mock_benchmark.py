
import asyncio
import time
from typing import List, Dict
from unittest.mock import MagicMock, patch

# Mocking Firestore
class MockDoc:
    def __init__(self, data):
        self._data = data
    def to_dict(self):
        return self._data
    @property
    def id(self):
        return self._data.get('id', 'mock_id')

class MockQuery:
    def __init__(self, docs):
        self.docs = docs
        self.call_count = 0
    def stream(self):
        self.call_count += 1
        for doc in self.docs:
            yield MockDoc(doc)
    def count(self):
        self.call_count += 1
        mock_aggregation = MagicMock()
        # Match real implementation: returns a list of AggregationResult
        mock_result = MagicMock()
        mock_result.value = len(self.docs)
        mock_aggregation.get.return_value = [mock_result]
        return mock_aggregation

class MockCollection:
    def __init__(self, docs):
        self.docs = docs
        self.query_count = 0
    def where(self, *args, **kwargs):
        self.query_count += 1
        # Filter docs based on item_id for simplicity
        item_id = None
        for arg in args:
            # Simple mock of FieldFilter('item_id', '==', item_id)
            if hasattr(arg, 'value'):
                 item_id = arg.value

        filtered_docs = [d for d in self.docs if d.get('item_id') == item_id]
        return MockQuery(filtered_docs)

    def document(self, id):
        mock_doc_ref = MagicMock()
        doc_data = next((d for d in self.docs if d.get('id') == id), None)
        mock_doc = MagicMock()
        mock_doc.exists = doc_data is not None
        mock_doc.to_dict.return_value = doc_data
        mock_doc_ref.get.return_value = mock_doc
        return mock_doc_ref

class MockFirestore:
    def __init__(self, docs_by_collection):
        self.collections = {name: MockCollection(docs) for name, docs in docs_by_collection.items()}
    def collection(self, name):
        return self.collections[name]
    def get_all(self, doc_refs):
        # doc_refs are MagicMocks from document()
        results = []
        for ref in doc_refs:
            results.append(ref.get())
        return results

# Current implementation (simplified)
async def current_get_item_note_count(db, item_ids: List[str]) -> Dict[str, int]:
    if not item_ids:
        return {}

    def get_single_count(item_id):
        notes_ref = db.collection('item_notes')
        # Simulate the current inefficient stream count
        query = notes_ref.where('item_id', '==', item_id)
        return sum(1 for _ in query.stream())

    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(None, get_single_count, item_id)
        for item_id in item_ids
    ]

    results = await asyncio.gather(*tasks)
    return dict(zip(item_ids, results))

# Optimized implementation using count() aggregation
async def optimized_get_item_note_count_aggregation(db, item_ids: List[str]) -> Dict[str, int]:
    if not item_ids:
        return {}

    def get_single_count(item_id):
        notes_ref = db.collection('item_notes')
        query = notes_ref.where('item_id', '==', item_id)
        # Match real implementation
        aggregation_query = query.count()
        results = aggregation_query.get()
        return results[0].value

    loop = asyncio.get_running_loop()
    tasks = [
        loop.run_in_executor(None, get_single_count, item_id)
        for item_id in item_ids
    ]

    results = await asyncio.gather(*tasks)
    return dict(zip(item_ids, results))

# Optimized implementation using denormalization (simulated)
async def optimized_get_item_note_count_denormalized(db, item_ids: List[str]) -> Dict[str, int]:
    if not item_ids:
        return {}

    def get_counts():
        doc_refs = [db.collection('shared_items').document(item_id) for item_id in item_ids]
        snapshots = db.get_all(doc_refs)
        counts = {}
        for snap in snapshots:
            data = snap.to_dict()
            counts[snap.id] = data.get('note_count', 0) if data else 0
        return counts

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, get_counts)

async def run_benchmark():
    num_items = 50
    notes_per_item = 100
    item_ids = [f"item_{i}" for i in range(num_items)]

    all_notes = []
    all_items = []
    for item_id in item_ids:
        all_items.append({'id': item_id, 'note_count': notes_per_item})
        for n in range(notes_per_item):
            all_notes.append({'id': f"note_{item_id}_{n}", 'item_id': item_id})

    docs = {
        'item_notes': all_notes,
        'shared_items': all_items
    }

    # 1. Baseline
    db = MockFirestore(docs)
    start = time.time()
    await current_get_item_note_count(db, item_ids)
    duration_current = time.time() - start
    queries_current = db.collection('item_notes').query_count
    # In current, we stream every doc.
    # Our mock stream() is called N times.

    print(f"Current implementation: {duration_current:.4f}s, Queries: {queries_current}")

    # 2. Aggregation
    db = MockFirestore(docs)
    start = time.time()
    await optimized_get_item_note_count_aggregation(db, item_ids)
    duration_agg = time.time() - start
    queries_agg = db.collection('item_notes').query_count
    print(f"Aggregation implementation: {duration_agg:.4f}s, Queries: {queries_agg}")

    # 3. Denormalization
    db = MockFirestore(docs)
    start = time.time()
    await optimized_get_item_note_count_denormalized(db, item_ids)
    duration_denorm = time.time() - start
    # query_count is 0 because we use get_all
    print(f"Denormalized implementation: {duration_denorm:.4f}s, Batch requests: 1")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
