import os
import base64
import datetime
from uuid import uuid4
import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import logging

from models import User, SharedItem, ItemNote, WorkerJobStatus

# Firestore imports
import firebase_admin
from firebase_admin import credentials, firestore
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.batch import WriteBatch

# SQLAlchemy imports
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer, inspect, text, func
from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer, inspect, text, func, update
from sqlalchemy.future import select

# --- Interface ---

class DatabaseInterface(ABC):
    @abstractmethod
    async def get_user(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    async def upsert_user(self, user: User) -> User:
        pass

    @abstractmethod
    async def create_shared_item(self, item: SharedItem) -> SharedItem:
        pass

    @abstractmethod
    async def get_shared_items(self, user_email: str) -> List[dict]:
        pass

    @abstractmethod
    async def validate_user_item_ownership(self, user_email: str, item_ids: List[str]) -> List[str]:
        pass

    @abstractmethod
    async def delete_shared_item(self, item_id: str, user_email: str) -> bool:
        pass

    @abstractmethod
    async def get_shared_item(self, item_id: str) -> Optional[dict]:
        pass

    @abstractmethod
    async def update_shared_item(self, item_id: str, updates: dict) -> bool:
        pass

    @abstractmethod
    async def get_items_by_status(self, status: str, limit: int = 10) -> List[dict]:
        pass

    @abstractmethod
    async def get_unnormalized_items(self, limit: int = 10) -> List[dict]:
        pass

    @abstractmethod
    async def get_normalized_items(self, limit: int = 10) -> List[dict]:
        pass

    @abstractmethod
    async def create_item_note(self, note: ItemNote) -> ItemNote:
        pass

    @abstractmethod
    async def get_item_notes(self, item_id: str) -> List[dict]:
        pass

    @abstractmethod
    async def update_item_note(self, note_id: str, updates: dict) -> bool:
        pass

    @abstractmethod
    async def delete_item_note(self, note_id: str, user_email: str) -> bool:
        pass

    @abstractmethod
    async def get_follow_up_notes(self, item_id: str) -> List[dict]:
        pass

    @abstractmethod
    async def get_item_note_count(self, item_ids: List[str]) -> Dict[str, int]:
        pass

    @abstractmethod
    async def get_user_tags(self, user_email: str) -> List[str]:
        pass

    @abstractmethod
    async def get_user_item_counts_by_status(self, user_email: str) -> Dict[str, int]:
        pass

    @abstractmethod
    async def get_user_worker_job_counts_by_status(self, user_email: str) -> Dict[str, int]:
        pass

    @abstractmethod
    async def enqueue_worker_job(self, item_id: str, user_email: str, job_type: str, payload: Optional[dict] = None) -> str:
        pass

    @abstractmethod
    async def lease_worker_jobs(self, job_type: str, worker_id: str, limit: int = 10, lease_seconds: int = 600) -> List[dict]:
        pass

    @abstractmethod
    async def complete_worker_job(self, job_id: str) -> bool:
        pass

    @abstractmethod
    async def fail_worker_job(self, job_id: str, error: str) -> bool:
        pass

    @abstractmethod
    async def reset_failed_jobs(self, job_type: str, error_msg: str) -> int:
        pass

    @abstractmethod
    async def get_failed_worker_jobs(self, job_type: Optional[str] = None, max_attempts: Optional[int] = None) -> List[dict]:
        pass

    @abstractmethod
    async def reset_worker_job(self, job_id: str) -> bool:
        pass

    @abstractmethod
    async def get_queued_job_counts_by_type(self) -> Dict[str, int]:
        """Returns {job_type: count} for all queued jobs."""
        pass

    @abstractmethod
    async def search_similar_items(self, embedding: List[float], user_email: str, limit: int = 10) -> List[dict]:
        pass


# --- Firestore Implementation ---

class FirestoreDatabase(DatabaseInterface):
    def __init__(self):
        # Initialize Firebase if not already done
        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={
                'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET')
            })
        self.db: FirestoreClient = firestore.client()

    def _encode_tag(self, tag: str) -> str:
        return base64.urlsafe_b64encode(tag.encode('utf-8')).decode('utf-8').rstrip('=')

    def _decode_tag(self, encoded_tag: str) -> str:
        padding = 4 - (len(encoded_tag) % 4)
        if padding != 4:
            encoded_tag += '=' * padding
        return base64.urlsafe_b64decode(encoded_tag.encode('utf-8')).decode('utf-8')

    def _get_tag_updates(self, added_tags: List[str], removed_tags: List[str]) -> dict:
        updates = {}
        for tag in added_tags:
            if not tag: continue
            key = f"tags.{self._encode_tag(tag)}"
            updates[key] = firestore.Increment(1)
        for tag in removed_tags:
            if not tag: continue
            key = f"tags.{self._encode_tag(tag)}"
            updates[key] = firestore.Increment(-1)
        return updates

    async def get_user(self, email: str) -> Optional[User]:
        doc = self.db.collection('users').document(email).get()
        if doc.exists:
            data = doc.to_dict()
            return User(**data)
        return None

    async def upsert_user(self, user: User) -> User:
        user_data = user.dict()
        user_data['updated_at'] = firestore.SERVER_TIMESTAMP
        self.db.collection('users').document(user.email).set(user_data, merge=True)
        return user

    async def create_shared_item(self, item: SharedItem) -> SharedItem:
        item_dict = item.dict()
        item_ref = self.db.collection('shared_items').document(item.id)

        # Extract tags for denormalization
        tags = []
        if item.analysis and item.analysis.tags:
            tags = item.analysis.tags

        loop = asyncio.get_running_loop()

        def _create_with_tags():
            transaction = self.db.transaction()

            @firestore.transactional
            def _txn(transaction):
                # Check if user_tags exists
                user_tags_ref = self.db.collection('user_tags').document(item.user_email)
                user_tags_doc = user_tags_ref.get(transaction=transaction)

                transaction.set(item_ref, item_dict)

                if user_tags_doc.exists and tags:
                    tag_updates = self._get_tag_updates(tags, [])
                    transaction.set(user_tags_ref, tag_updates, merge=True)

            _txn(transaction)

        await loop.run_in_executor(None, _create_with_tags)
        return item

    async def get_shared_items(self, user_email: str) -> List[dict]:
        items_ref = self.db.collection('shared_items')
        query = items_ref.where(
            filter=FieldFilter('user_email', '==', user_email)
        ).order_by('created_at', direction=firestore.Query.DESCENDING)

        def get_docs():
            items = []
            for doc in query.stream():
                data = doc.to_dict()
                data['firestore_id'] = doc.id
                items.append(data)
            return items

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_docs)

    async def validate_user_item_ownership(self, user_email: str, item_ids: List[str]) -> List[str]:
        if not item_ids:
            return []

        def validate():
            authorized_ids = []
            # Firestore get_all can take many document references.
            # We chunk them to be safe and efficient.
            for i in range(0, len(item_ids), 100):
                chunk = item_ids[i:i + 100]
                doc_refs = [self.db.collection('shared_items').document(tid) for tid in chunk]
                snapshots = self.db.get_all(doc_refs)
                for snap in snapshots:
                    if snap.exists:
                        data = snap.to_dict()
                        if data.get('user_email') == user_email:
                            authorized_ids.append(snap.id)
            return authorized_ids

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, validate)

    async def delete_shared_item(self, item_id: str, user_email: str) -> bool:
        item_ref = self.db.collection('shared_items').document(item_id)

        loop = asyncio.get_running_loop()

        def _delete_with_tags():
            transaction = self.db.transaction()

            @firestore.transactional
            def _txn(transaction):
                doc = item_ref.get(transaction=transaction)
                if not doc.exists:
                    return False

                item_data = doc.to_dict()
                if item_data.get('user_email') != user_email:
                    # Raises error which aborts transaction
                    raise ValueError("Forbidden")

                # Calculate removed tags
                analysis = item_data.get('analysis') or {}
                tags = analysis.get('tags') or []

                transaction.delete(item_ref)

                if tags:
                    user_tags_ref = self.db.collection('user_tags').document(user_email)
                    user_tags_doc = user_tags_ref.get(transaction=transaction)

                    if user_tags_doc.exists:
                        tag_updates = self._get_tag_updates([], tags)
                        transaction.set(user_tags_ref, tag_updates, merge=True)

                return True

            return _txn(transaction)

        return await loop.run_in_executor(None, _delete_with_tags)

    async def get_shared_item(self, item_id: str) -> Optional[dict]:
        doc = self.db.collection('shared_items').document(item_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['firestore_id'] = doc.id
            return data
        return None

    async def update_shared_item(self, item_id: str, updates: dict) -> bool:
        item_ref = self.db.collection('shared_items').document(item_id)

        # Check if analysis tags are being updated
        check_tags = 'analysis' in updates

        loop = asyncio.get_running_loop()

        def _update_with_tags():
            if not check_tags:
                try:
                    item_ref.update(updates)
                    return True
                except Exception:
                    return False

            transaction = self.db.transaction()

            @firestore.transactional
            def _txn(transaction):
                doc = item_ref.get(transaction=transaction)
                if not doc.exists:
                    return False

                item_data = doc.to_dict()

                # Apply update in transaction
                transaction.update(item_ref, updates)

                # Calculate tag diff
                old_analysis = item_data.get('analysis') or {}
                old_tags = set(old_analysis.get('tags') or [])

                new_analysis = updates.get('analysis') or {}
                # If tags key is not present in new analysis, assume it's unchanged?
                # Or if analysis is replaced entirely?
                # Usually updates['analysis'] replaces the whole analysis object or fields within it?
                # The caller usually passes the full analysis object.
                # Let's assume safely:
                new_tags = set(new_analysis.get('tags') or [])

                # Wait, if `updates` is a partial update to the document, `analysis` key replaces `analysis` field.
                # So `new_tags` IS the new state of tags.
                # HOWEVER, if `updates` merges analysis fields (e.g. dot notation), logic differs.
                # But Firestore update(dict) replaces top-level keys.
                # `main.py` sends `{'analysis': ...}`. So it replaces analysis.

                added_tags = list(new_tags - old_tags)
                removed_tags = list(old_tags - new_tags)

                if added_tags or removed_tags:
                    user_email = item_data.get('user_email')
                    if user_email:
                        user_tags_ref = self.db.collection('user_tags').document(user_email)
                        user_tags_doc = user_tags_ref.get(transaction=transaction)

                        if user_tags_doc.exists:
                            tag_updates = self._get_tag_updates(added_tags, removed_tags)
                            transaction.set(user_tags_ref, tag_updates, merge=True)

                return True

            try:
                return _txn(transaction)
            except Exception:
                return False

        return await loop.run_in_executor(None, _update_with_tags)

    async def get_items_by_status(self, status: str, limit: int = 10) -> List[dict]:
        items_ref = self.db.collection('shared_items')
        query = items_ref.where(
            filter=FieldFilter('status', '==', status)
        ).limit(limit)

        def get_docs():
            items = []
            for doc in query.stream():
                data = doc.to_dict()
                data['firestore_id'] = doc.id
                items.append(data)
            return items

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_docs)

    async def get_unnormalized_items(self, limit: int = 10) -> List[dict]:
        # Note: This will only find items where is_normalized is explicitly False.
        # Items missing the field (legacy) will need a backfill or manual processing if they need normalization.
        items_ref = self.db.collection('shared_items')
        query = items_ref.where(field_path='is_normalized', op_string='==', value=False).limit(limit)

        def get_docs():
            items = []
            for doc in query.stream():
                data = doc.to_dict()
                data['firestore_id'] = doc.id
                items.append(data)
            return items

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_docs)

    async def get_normalized_items(self, limit: int = 10) -> List[dict]:
        items_ref = self.db.collection('shared_items')
        query = items_ref.where(field_path='is_normalized', op_string='==', value=True).limit(limit)

        def get_docs():
            items = []
            for doc in query.stream():
                data = doc.to_dict()
                data['firestore_id'] = doc.id
                items.append(data)
            return items

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_docs)

    async def create_item_note(self, note: ItemNote) -> ItemNote:
        note_dict = {
            'id': note.id,
            'item_id': note.item_id,
            'user_email': note.user_email,
            'text': note.text,
            'image_path': note.image_path,
            'note_type': note.note_type,
            'created_at': note.created_at,
            'updated_at': note.updated_at,
        }
        self.db.collection('item_notes').document(note.id).set(note_dict)
        return note

    async def get_item_notes(self, item_id: str) -> List[dict]:
        notes_ref = self.db.collection('item_notes')
        query = notes_ref.where(
            filter=FieldFilter('item_id', '==', item_id)
        ).order_by('created_at', direction=firestore.Query.ASCENDING)

        def get_docs():
            notes = []
            for doc in query.stream():
                data = doc.to_dict()
                notes.append(data)
            return notes

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_docs)

    async def get_follow_up_notes(self, item_id: str) -> List[dict]:
        notes_ref = self.db.collection('item_notes')
        query = notes_ref.where(
            filter=FieldFilter('item_id', '==', item_id)
        ).where(
            filter=FieldFilter('note_type', '==', 'follow_up')
        ).order_by('created_at', direction=firestore.Query.ASCENDING)

        def get_docs():
            notes = []
            for doc in query.stream():
                data = doc.to_dict()
                notes.append(data)
            return notes

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_docs)

    async def update_item_note(self, note_id: str, updates: dict) -> bool:
        note_ref = self.db.collection('item_notes').document(note_id)
        doc = note_ref.get()
        if not doc.exists:
            return False

        # Check ownership if user_email provided
        user_email = updates.pop('user_email', None)
        if user_email:
            note_data = doc.to_dict()
            if note_data.get('user_email') != user_email:
                raise ValueError("Forbidden")

        updates['updated_at'] = datetime.datetime.utcnow()
        note_ref.update(updates)
        return True

    async def delete_item_note(self, note_id: str, user_email: str) -> bool:
        note_ref = self.db.collection('item_notes').document(note_id)
        doc = note_ref.get()
        if not doc.exists:
            return False

        note_data = doc.to_dict()
        if note_data.get('user_email') != user_email:
            raise ValueError("Forbidden")

        note_ref.delete()
        return True

    async def get_item_note_count(self, item_ids: List[str]) -> Dict[str, int]:
        if not item_ids:
            return {}

        def get_single_count(item_id):
            # Firestore doesn't support COUNT aggregation well, so we fetch and count
            # For better performance with large datasets, consider using a counter field
            notes_ref = self.db.collection('item_notes')
            query = notes_ref.where(filter=FieldFilter('item_id', '==', item_id))
            return sum(1 for _ in query.stream())

        loop = asyncio.get_running_loop()
        tasks = [
            loop.run_in_executor(None, get_single_count, item_id)
            for item_id in item_ids
        ]

        results = await asyncio.gather(*tasks)
        return dict(zip(item_ids, results))

    async def get_user_tags(self, user_email: str) -> List[str]:
        def get_tags():
            # Try fetching from denormalized collection
            user_tags_ref = self.db.collection('user_tags').document(user_email)
            doc = user_tags_ref.get()

            if doc.exists:
                data = doc.to_dict() or {}
                tags_map = data.get('tags') or {}
                # Return tags with count > 0
                return sorted([
                    self._decode_tag(k)
                    for k, count in tags_map.items()
                    if count > 0
                ], key=str.lower)

            # Fallback / Backfill
            items_ref = self.db.collection('shared_items')
            query = items_ref.where(filter=FieldFilter('user_email', '==', user_email))

            tags_map = {} # tag -> count

            for doc in query.stream():
                data = doc.to_dict() or {}
                analysis = data.get('analysis') or {}
                raw_tags = analysis.get('tags') or []
                if isinstance(raw_tags, list):
                    for tag in raw_tags:
                        tag_str = str(tag).strip()
                        if tag_str:
                            tags_map[tag_str] = tags_map.get(tag_str, 0) + 1

            # Save to user_tags for next time
            if tags_map:
                updates = {}
                for tag, count in tags_map.items():
                    key = f"tags.{self._encode_tag(tag)}"
                    updates[key] = count # Set absolute value for initial backfill

                # We use set(..., merge=True) to avoid overwriting other potential fields
                user_tags_ref.set(updates, merge=True)

            return sorted(tags_map.keys(), key=str.lower)

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_tags)

    async def get_user_item_counts_by_status(self, user_email: str) -> Dict[str, int]:
        def get_counts():
            items_ref = self.db.collection('shared_items')
            query = items_ref.where(filter=FieldFilter('user_email', '==', user_email))

            counts = {}
            for doc in query.stream():
                data = doc.to_dict()
                status = data.get('status', 'new')
                counts[status] = counts.get(status, 0) + 1
            return counts

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_counts)

    async def get_user_worker_job_counts_by_status(self, user_email: str) -> Dict[str, int]:
        def get_counts():
            jobs_ref = self.db.collection('worker_queue')
            query = jobs_ref.where(filter=FieldFilter('user_email', '==', user_email))

            counts = {}
            for doc in query.stream():
                data = doc.to_dict()
                status = data.get('status', WorkerJobStatus.queued.value)
                counts[status] = counts.get(status, 0) + 1
            return counts

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_counts)

    async def enqueue_worker_job(self, item_id: str, user_email: str, job_type: str, payload: Optional[dict] = None) -> str:
        job_data = {
            'item_id': item_id,
            'user_email': user_email,
            'job_type': job_type,
            'status': WorkerJobStatus.queued.value,
            'attempts': 0,
            'payload': payload or {},
            'created_at': firestore.SERVER_TIMESTAMP,
            'updated_at': firestore.SERVER_TIMESTAMP
        }
        doc_ref = self.db.collection('worker_queue').document()
        doc_ref.set(job_data)
        return doc_ref.id

    async def lease_worker_jobs(self, job_type: str, worker_id: str, limit: int = 10, lease_seconds: int = 600) -> List[dict]:
        def lease():
            now = datetime.datetime.now(datetime.timezone.utc)
            lease_expires_at = now + datetime.timedelta(seconds=lease_seconds)
            jobs = []
            query = (
                self.db.collection('worker_queue')
                .where(filter=FieldFilter('job_type', '==', job_type))
                .where(filter=FieldFilter('status', '==', WorkerJobStatus.queued.value))
                .order_by('created_at')
                .limit(limit)
            )

            for doc in query.stream():
                transaction = self.db.transaction()

                @firestore.transactional
                def _claim(transaction):
                    snapshot = doc.reference.get(transaction=transaction)
                    data = snapshot.to_dict() or {}
                    if data.get('status') != WorkerJobStatus.queued.value:
                        return
                    attempts = int(data.get('attempts', 0)) + 1
                    transaction.update(doc.reference, {
                        'status': WorkerJobStatus.leased.value,
                        'worker_id': worker_id,
                        'lease_expires_at': lease_expires_at,
                        'attempts': attempts,
                        'updated_at': firestore.SERVER_TIMESTAMP
                    })
                    data['firestore_id'] = snapshot.id
                    data['status'] = WorkerJobStatus.leased.value
                    data['worker_id'] = worker_id
                    data['lease_expires_at'] = lease_expires_at
                    data['attempts'] = attempts
                    jobs.append(data)

                _claim(transaction)

            return jobs

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lease)

    async def complete_worker_job(self, job_id: str) -> bool:
        job_ref = self.db.collection('worker_queue').document(job_id)
        doc = job_ref.get()
        if not doc.exists:
            return False
        job_ref.update({
            'status': WorkerJobStatus.completed.value,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        return True

    async def fail_worker_job(self, job_id: str, error: str) -> bool:
        job_ref = self.db.collection('worker_queue').document(job_id)
        doc = job_ref.get()
        if not doc.exists:
            return False
        job_ref.update({
            'status': WorkerJobStatus.failed.value,
            'error': error,
            'updated_at': firestore.SERVER_TIMESTAMP
        })
        return True

    async def reset_failed_jobs(self, job_type: str, error_msg: str) -> int:
        job_ref = self.db.collection('worker_queue')
        query = (
            job_ref
            .where(filter=FieldFilter('job_type', '==', job_type))
            .where(filter=FieldFilter('status', '==', WorkerJobStatus.failed.value))
            .where(filter=FieldFilter('error', '==', error_msg))
        )
        
        count = 0
        batch = self.db.batch()
        
        for doc in query.stream():
            batch.update(doc.reference, {
                'status': WorkerJobStatus.queued.value,
                'error': firestore.DELETE_FIELD,
                'attempts': 0,
                'updated_at': firestore.SERVER_TIMESTAMP
            })
            count += 1
            if count % 400 == 0:
                batch.commit()
                batch = self.db.batch()
        
        if count % 400 != 0 or count == 0:
            # Commit remaining or if we had a batch that wasn't committed yet (though count==0 means empty batch)
            # Safe to commit empty batch? Yes.
            batch.commit()
            
        return count

    async def get_failed_worker_jobs(self, job_type: Optional[str] = None, max_attempts: Optional[int] = None) -> List[dict]:
        def get_jobs():
            query = (
                self.db.collection('worker_queue')
                .where(filter=FieldFilter('status', '==', WorkerJobStatus.failed.value))
            )
            if job_type:
                query = query.where(filter=FieldFilter('job_type', '==', job_type))

            results = []
            for doc in query.stream():
                data = doc.to_dict()
                data['firestore_id'] = doc.id
                attempts = int(data.get('attempts', 0))
                if max_attempts is not None and attempts > max_attempts:
                    continue
                results.append(data)
            return results

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_jobs)

    async def reset_worker_job(self, job_id: str) -> bool:
        job_ref = self.db.collection('worker_queue').document(job_id)
        doc = job_ref.get()
        if not doc.exists:
            return False
        job_ref.update({
            'status': WorkerJobStatus.queued.value,
            'error': firestore.DELETE_FIELD,
            'worker_id': firestore.DELETE_FIELD,
            'lease_expires_at': firestore.DELETE_FIELD,
        })
        return True

    async def get_queued_job_counts_by_type(self) -> Dict[str, int]:
        def get_counts():
            query = (
                self.db.collection('worker_queue')
                .where(filter=FieldFilter('status', '==', WorkerJobStatus.queued.value))
            )
            counts = {}
            for doc in query.stream():
                data = doc.to_dict()
                job_type = data.get('job_type', 'unknown')
                counts[job_type] = counts.get(job_type, 0) + 1
            return counts

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, get_counts)

    async def search_similar_items(self, embedding: List[float], user_email: str, limit: int = 10) -> List[dict]:
        # Firestore Vector Search using `find_nearest`
        try:
            from google.cloud.firestore_v1.vector import Vector
            
            # Create a vector from the list of floats
            query_vector = Vector(embedding)
            
            items_ref = self.db.collection('shared_items')
            
            # Initial query with user filter
            base_query = items_ref.where(filter=FieldFilter('user_email', '==', user_email))

            # Use find_nearest on the filtered query
            # Note: This requires a composite index including the vector field and user_email
            query = base_query.find_nearest(
                vector_field="embedding",
                query_vector=query_vector,
                distance_measure="COSINE",
                limit=limit
            )
            
            results = []
            for doc in query.stream():
                data = doc.to_dict()
                data['firestore_id'] = doc.id
                results.append(data)
                
            return results
        except ImportError:
            # Fallback if vector search is not available in the library version
            logging.error("google.cloud.firestore_v1.vector not available")
            return []
        except Exception as e:
            logging.error(f"Vector search failed: {e}")
            return []


# --- SQLite Implementation ---

Base = declarative_base()

class DBUser(Base):
    __tablename__ = 'users'
    email = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
    timezone = Column(String, default="America/New_York")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DBSharedItem(Base):
    __tablename__ = 'shared_items'
    id = Column(String, primary_key=True) # UUID
    user_email = Column(String)
    title = Column(String, nullable=True)
    content = Column(String)
    type = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    item_metadata = Column(JSON, nullable=True)
    analysis = Column(JSON, nullable=True)
    status = Column(String, default='new')
    next_step = Column(String, nullable=True)
    is_normalized = Column(Boolean, default=False)
    hidden = Column(Boolean, default=False)
    embedding = Column(JSON, nullable=True)

class DBItemNote(Base):
    __tablename__ = 'item_notes'
    id = Column(String, primary_key=True)
    item_id = Column(String, nullable=False, index=True)
    user_email = Column(String, nullable=False)
    text = Column(String, nullable=True)
    image_path = Column(String, nullable=True)
    note_type = Column(String, default='context')
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class DBWorkerJob(Base):
    __tablename__ = 'worker_queue'
    id = Column(String, primary_key=True)
    item_id = Column(String, nullable=False, index=True)
    user_email = Column(String, nullable=False)
    job_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default='queued')
    attempts = Column(Integer, default=0)
    worker_id = Column(String, nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    error = Column(String, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)

class SQLiteDatabase(DatabaseInterface):
    def __init__(self, db_url: str = "sqlite+aiosqlite:///./development.db"):
        self.engine = create_async_engine(db_url, echo=False)
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def init_db(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

            def ensure_hidden_column(sync_conn):
                inspector = inspect(sync_conn)
                columns = [col['name'] for col in inspector.get_columns('shared_items')]
                if 'hidden' not in columns:
                    sync_conn.execute(text("ALTER TABLE shared_items ADD COLUMN hidden BOOLEAN DEFAULT 0"))

            await conn.run_sync(ensure_hidden_column)

            def ensure_item_notes_table(sync_conn):
                inspector = inspect(sync_conn)
                if 'item_notes' not in inspector.get_table_names():
                    # Create the item_notes table for existing databases
                    sync_conn.execute(text("""
                        CREATE TABLE item_notes (
                            id VARCHAR PRIMARY KEY,
                            item_id VARCHAR NOT NULL,
                            user_email VARCHAR NOT NULL,
                            text VARCHAR,
                            image_path VARCHAR,
                            created_at DATETIME,
                            updated_at DATETIME
                        )
                    """))
                    sync_conn.execute(text("CREATE INDEX ix_item_notes_item_id ON item_notes (item_id)"))

            await conn.run_sync(ensure_item_notes_table)

            def ensure_note_type_column(sync_conn):
                inspector = inspect(sync_conn)
                columns = [col['name'] for col in inspector.get_columns('item_notes')]
                if 'note_type' not in columns:
                    sync_conn.execute(text("ALTER TABLE item_notes ADD COLUMN note_type VARCHAR DEFAULT 'context'"))

            await conn.run_sync(ensure_note_type_column)

            def ensure_worker_queue_table(sync_conn):
                inspector = inspect(sync_conn)
                if 'worker_queue' not in inspector.get_table_names():
                    sync_conn.execute(text("""
                        CREATE TABLE worker_queue (
                            id VARCHAR PRIMARY KEY,
                            item_id VARCHAR NOT NULL,
                            user_email VARCHAR NOT NULL,
                            job_type VARCHAR NOT NULL,
                            status VARCHAR NOT NULL,
                            attempts INTEGER,
                            worker_id VARCHAR,
                            lease_expires_at DATETIME,
                            error VARCHAR,
                            payload JSON,
                            created_at DATETIME,
                            updated_at DATETIME
                        )
                    """))
                    sync_conn.execute(text("CREATE INDEX ix_worker_queue_item_id ON worker_queue (item_id)"))
                    sync_conn.execute(text("CREATE INDEX ix_worker_queue_job_type ON worker_queue (job_type)"))
                    sync_conn.execute(text("CREATE INDEX ix_worker_queue_status ON worker_queue (status)"))

            await conn.run_sync(ensure_worker_queue_table)

            def ensure_user_timezone_column(sync_conn):
                inspector = inspect(sync_conn)
                columns = [col['name'] for col in inspector.get_columns('users')]
                if 'timezone' not in columns:
                    sync_conn.execute(text("ALTER TABLE users ADD COLUMN timezone VARCHAR DEFAULT 'America/New_York'"))

            await conn.run_sync(ensure_user_timezone_column)

    async def close(self):
        await self.engine.dispose()

    async def get_user(self, email: str) -> Optional[User]:
        async with self.SessionLocal() as session:
            result = await session.execute(select(DBUser).where(DBUser.email == email))
            db_user = result.scalar_one_or_none()
            if db_user:
                return User(
                    email=db_user.email,
                    name=db_user.name,
                    picture=db_user.picture,
                    timezone=db_user.timezone or "America/New_York",
                    created_at=db_user.created_at
                )
            return None

    async def search_similar_items(self, embedding: List[float], user_email: str, limit: int = 10) -> List[dict]:
        # SQLite doesn't support vector search easily. Return empty.
        # Could implement basic cosine similarity in python if needed but slow.
        return []

    async def upsert_user(self, user: User) -> User:
        async with self.SessionLocal() as session:
            result = await session.execute(select(DBUser).where(DBUser.email == user.email))
            db_user = result.scalar_one_or_none()

            if db_user:
                db_user.name = user.name
                db_user.picture = user.picture
                # update timestamp?
            else:
                db_user = DBUser(
                    email=user.email,
                    name=user.name,
                    picture=user.picture,
                    timezone=user.timezone,
                    created_at=user.created_at or datetime.datetime.now(datetime.timezone.utc)
                )
                session.add(db_user)

            await session.commit()
            return user

    async def create_shared_item(self, item: SharedItem) -> SharedItem:
        async with self.SessionLocal() as session:
            # Convert Pydantic models to dicts for JSON columns if needed
            analysis_data = None
            if item.analysis:
                if hasattr(item.analysis, 'model_dump'):
                    analysis_data = item.analysis.model_dump()
                elif hasattr(item.analysis, 'dict'):
                    analysis_data = item.analysis.dict()
                else:
                    analysis_data = item.analysis

            db_item = DBSharedItem(
                id=str(item.id),
                user_email=item.user_email,
                title=item.title,
                content=item.content,
                type=item.type,
                created_at=item.created_at or datetime.datetime.now(datetime.timezone.utc),
                item_metadata=item.item_metadata,
                analysis=analysis_data,
                status=item.status,
                next_step=item.next_step,
                is_normalized=item.is_normalized,
                hidden=item.hidden,
                embedding=item.embedding
            )
            session.add(db_item)
            await session.commit()
            return item

    async def get_shared_items(self, user_email: str) -> List[dict]:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBSharedItem)
                .where(DBSharedItem.user_email == user_email)
                .order_by(DBSharedItem.created_at.desc())
            )
            items = result.scalars().all()

            # Convert to dict format matching Firestore output
            return [
                {
                    'firestore_id': item.id, # Map UUID to firestore_id for frontend compatibility
                    'title': item.title,
                    'content': item.content,
                    'type': item.type,
                    'user_email': item.user_email,
                    'created_at': item.created_at,
                    'item_metadata': item.item_metadata,
                    'analysis': item.analysis,
                    'status': item.status,
                    'next_step': item.next_step,
                    'is_normalized': item.is_normalized,
                    'hidden': item.hidden
                }
                for item in items
            ]

    async def validate_user_item_ownership(self, user_email: str, item_ids: List[str]) -> List[str]:
        if not item_ids:
            return []
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBSharedItem.id)
                .where(DBSharedItem.user_email == user_email)
                .where(DBSharedItem.id.in_(item_ids))
            )
            return [row[0] for row in result.all()]

    async def delete_shared_item(self, item_id: str, user_email: str) -> bool:
        async with self.SessionLocal() as session:
            result = await session.execute(select(DBSharedItem).where(DBSharedItem.id == item_id))
            item = result.scalar_one_or_none()

            if not item:
                return False

            if item.user_email != user_email:
                raise ValueError("Forbidden")

            await session.delete(item)
            await session.commit()
            return True

    async def get_shared_item(self, item_id: str) -> Optional[dict]:
        async with self.SessionLocal() as session:
            result = await session.execute(select(DBSharedItem).where(DBSharedItem.id == item_id))
            item = result.scalar_one_or_none()
            if item:
                 return {
                    'firestore_id': item.id,
                    'title': item.title,
                    'content': item.content,
                    'type': item.type,
                    'user_email': item.user_email,
                    'created_at': item.created_at,
                    'analysis': item.analysis,
                    'status': item.status,
                    'next_step': item.next_step,
                    'is_normalized': item.is_normalized,
                    'hidden': item.hidden
                }
            return None

    async def update_shared_item(self, item_id: str, updates: dict) -> bool:
        async with self.SessionLocal() as session:
            result = await session.execute(select(DBSharedItem).where(DBSharedItem.id == item_id))
            item = result.scalar_one_or_none()
            if not item:
                return False

            for key, value in updates.items():
                if hasattr(item, key):
                     setattr(item, key, value)

            await session.commit()
            return True

    async def get_items_by_status(self, status: str, limit: int = 10) -> List[dict]:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBSharedItem)
                .where(DBSharedItem.status == status)
                .limit(limit)
            )
            items = result.scalars().all()

            return [
                {
                    'firestore_id': item.id,
                    'title': item.title,
                    'content': item.content,
                    'type': item.type,
                    'user_email': item.user_email,
                    'created_at': item.created_at,
                    'item_metadata': item.item_metadata,
                    'analysis': item.analysis,
                    'status': item.status,
                    'next_step': item.next_step,
                    'is_normalized': item.is_normalized
                }
                for item in items
            ]

    async def get_unnormalized_items(self, limit: int = 10) -> List[dict]:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBSharedItem)
                .where(DBSharedItem.is_normalized == False)
                .limit(limit)
            )
            items = result.scalars().all()

            return [
                {
                    'firestore_id': item.id,
                    'title': item.title,
                    'content': item.content,
                    'type': item.type,
                    'user_email': item.user_email,
                    'created_at': item.created_at,
                    'item_metadata': item.item_metadata,
                    'analysis': item.analysis,
                    'status': item.status,
                    'next_step': item.next_step,
                    'is_normalized': item.is_normalized,
                    'hidden': item.hidden
                }
                for item in items
            ]

    async def get_normalized_items(self, limit: int = 10) -> List[dict]:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBSharedItem)
                .where(DBSharedItem.is_normalized == True)
                .limit(limit)
            )
            items = result.scalars().all()

            return [
                {
                    'firestore_id': item.id,
                    'title': item.title,
                    'content': item.content,
                    'type': item.type,
                    'user_email': item.user_email,
                    'created_at': item.created_at,
                    'item_metadata': item.item_metadata,
                    'analysis': item.analysis,
                    'status': item.status,
                    'next_step': item.next_step,
                    'is_normalized': item.is_normalized,
                    'hidden': item.hidden
                }
                for item in items
            ]

    async def create_item_note(self, note: ItemNote) -> ItemNote:
        async with self.SessionLocal() as session:
            db_note = DBItemNote(
                id=str(note.id),
                item_id=note.item_id,
                user_email=note.user_email,
                text=note.text,
                image_path=note.image_path,
                note_type=note.note_type,
                created_at=note.created_at or datetime.datetime.utcnow(),
                updated_at=note.updated_at or datetime.datetime.utcnow()
            )
            session.add(db_note)
            await session.commit()
            return note

    async def reset_failed_jobs(self, job_type: str, error_msg: str) -> int:
        async with self.SessionLocal() as session:
            stmt = (
                update(DBWorkerJob)
                .where(DBWorkerJob.job_type == job_type)
                .where(DBWorkerJob.status == 'failed')
                .where(DBWorkerJob.error == error_msg)
                .values(
                    status='queued', 
                    error=None, 
                    attempts=0, 
                    updated_at=datetime.datetime.utcnow()
                )
            )
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount

    async def get_failed_worker_jobs(self, job_type: Optional[str] = None, max_attempts: Optional[int] = None) -> List[dict]:
        async with self.SessionLocal() as session:
            query = select(DBWorkerJob).where(DBWorkerJob.status == 'failed')
            if job_type:
                query = query.where(DBWorkerJob.job_type == job_type)
            if max_attempts is not None:
                query = query.where(DBWorkerJob.attempts <= max_attempts)

            result = await session.execute(query)
            jobs = result.scalars().all()
            return [
                {
                    'firestore_id': job.id,
                    'item_id': job.item_id,
                    'user_email': job.user_email,
                    'job_type': job.job_type,
                    'status': job.status,
                    'attempts': job.attempts,
                    'error': job.error,
                    'created_at': job.created_at.isoformat() if job.created_at else None,
                    'updated_at': job.updated_at.isoformat() if job.updated_at else None,
                }
                for job in jobs
            ]

    async def reset_worker_job(self, job_id: str) -> bool:
        async with self.SessionLocal() as session:
            result = await session.execute(select(DBWorkerJob).where(DBWorkerJob.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                return False
            job.status = WorkerJobStatus.queued.value
            job.error = None
            job.worker_id = None
            job.lease_expires_at = None
            job.updated_at = datetime.datetime.now(datetime.timezone.utc)
            await session.commit()
            return True

    async def get_queued_job_counts_by_type(self) -> Dict[str, int]:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBWorkerJob.job_type, func.count(DBWorkerJob.id))
                .where(DBWorkerJob.status == WorkerJobStatus.queued.value)
                .group_by(DBWorkerJob.job_type)
            )
            rows = result.all()
            return {job_type: count for job_type, count in rows}

    async def get_item_notes(self, item_id: str) -> List[dict]:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBItemNote)
                .where(DBItemNote.item_id == item_id)
                .order_by(DBItemNote.created_at.asc())
            )
            notes = result.scalars().all()

            return [
                {
                    'id': note.id,
                    'item_id': note.item_id,
                    'user_email': note.user_email,
                    'text': note.text,
                    'image_path': note.image_path,
                    'note_type': note.note_type,
                    'created_at': note.created_at,
                    'updated_at': note.updated_at
                }
                for note in notes
            ]

    async def get_follow_up_notes(self, item_id: str) -> List[dict]:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBItemNote)
                .where(DBItemNote.item_id == item_id)
                .where(DBItemNote.note_type == 'follow_up')
                .order_by(DBItemNote.created_at.asc())
            )
            notes = result.scalars().all()
            return [
                {
                    'id': note.id,
                    'item_id': note.item_id,
                    'user_email': note.user_email,
                    'text': note.text,
                    'image_path': note.image_path,
                    'note_type': note.note_type,
                    'created_at': note.created_at,
                    'updated_at': note.updated_at
                }
                for note in notes
            ]

    async def update_item_note(self, note_id: str, updates: dict) -> bool:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBItemNote).where(DBItemNote.id == note_id)
            )
            note = result.scalar_one_or_none()
            if not note:
                return False

            # Verify ownership if user_email is provided in updates
            user_email = updates.pop('user_email', None)
            if user_email and note.user_email != user_email:
                raise ValueError("Forbidden")

            for key, value in updates.items():
                if hasattr(note, key):
                    setattr(note, key, value)

            note.updated_at = datetime.datetime.utcnow()
            await session.commit()
            return True

    async def delete_item_note(self, note_id: str, user_email: str) -> bool:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBItemNote).where(DBItemNote.id == note_id)
            )
            note = result.scalar_one_or_none()

            if not note:
                return False

            if note.user_email != user_email:
                raise ValueError("Forbidden")

            await session.delete(note)
            await session.commit()
            return True

    async def get_item_note_count(self, item_ids: List[str]) -> Dict[str, int]:
        async with self.SessionLocal() as session:
            if not item_ids:
                return {}

            result = await session.execute(
                select(DBItemNote.item_id, func.count(DBItemNote.id))
                .where(DBItemNote.item_id.in_(item_ids))
                .group_by(DBItemNote.item_id)
            )
            rows = result.all()

            # Initialize all requested item_ids with 0, then update with actual counts
            counts = {item_id: 0 for item_id in item_ids}
            for item_id, count in rows:
                counts[item_id] = count

            return counts

    async def get_user_tags(self, user_email: str) -> List[str]:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBSharedItem.analysis)
                .where(DBSharedItem.user_email == user_email)
            )
            rows = result.all()
            tags = set()
            for (analysis,) in rows:
                analysis = analysis or {}
                raw_tags = analysis.get('tags') or []
                if isinstance(raw_tags, list):
                    for tag in raw_tags:
                        tag_str = str(tag).strip()
                        if tag_str:
                            tags.add(tag_str)
            return sorted(tags, key=str.lower)

    async def get_user_item_counts_by_status(self, user_email: str) -> Dict[str, int]:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBSharedItem.status, func.count(DBSharedItem.id))
                .where(DBSharedItem.user_email == user_email)
                .group_by(DBSharedItem.status)
            )
            rows = result.all()

            counts = {}
            for status, count in rows:
                counts[status or 'new'] = count

            return counts

    async def get_user_worker_job_counts_by_status(self, user_email: str) -> Dict[str, int]:
        async with self.SessionLocal() as session:
            result = await session.execute(
                select(DBWorkerJob.status, func.count(DBWorkerJob.id))
                .where(DBWorkerJob.user_email == user_email)
                .group_by(DBWorkerJob.status)
            )
            rows = result.all()

            counts = {}
            for status, count in rows:
                counts[status or WorkerJobStatus.queued.value] = count

            return counts

    async def enqueue_worker_job(self, item_id: str, user_email: str, job_type: str, payload: Optional[dict] = None) -> str:
        async with self.SessionLocal() as session:
            job_id = str(uuid4())
            now = datetime.datetime.now(datetime.timezone.utc)
            job = DBWorkerJob(
                id=job_id,
                item_id=item_id,
                user_email=user_email,
                job_type=job_type,
                status=WorkerJobStatus.queued.value,
                attempts=0,
                payload=payload or {},
                created_at=now,
                updated_at=now
            )
            session.add(job)
            await session.commit()
            return job_id

    async def lease_worker_jobs(self, job_type: str, worker_id: str, limit: int = 10, lease_seconds: int = 600) -> List[dict]:
        async with self.SessionLocal() as session:
            now = datetime.datetime.now(datetime.timezone.utc)
            lease_expires_at = now + datetime.timedelta(seconds=lease_seconds)

            result = await session.execute(
                select(DBWorkerJob)
                .where(DBWorkerJob.job_type == job_type)
                .where(DBWorkerJob.status == WorkerJobStatus.queued.value)
                .order_by(DBWorkerJob.created_at.asc())
                .limit(limit)
            )
            jobs = result.scalars().all()

            leased = []
            for job in jobs:
                job.status = WorkerJobStatus.leased.value
                job.worker_id = worker_id
                job.lease_expires_at = lease_expires_at
                job.attempts = (job.attempts or 0) + 1
                job.updated_at = now
                leased.append({
                    'firestore_id': job.id,
                    'item_id': job.item_id,
                    'user_email': job.user_email,
                    'job_type': job.job_type,
                    'status': job.status,
                    'attempts': job.attempts,
                    'worker_id': job.worker_id,
                    'lease_expires_at': job.lease_expires_at,
                    'payload': job.payload
                })

            await session.commit()
            return leased

    async def complete_worker_job(self, job_id: str) -> bool:
        async with self.SessionLocal() as session:
            result = await session.execute(select(DBWorkerJob).where(DBWorkerJob.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                return False
            job.status = WorkerJobStatus.completed.value
            job.updated_at = datetime.datetime.now(datetime.timezone.utc)
            await session.commit()
            return True

    async def fail_worker_job(self, job_id: str, error: str) -> bool:
        async with self.SessionLocal() as session:
            result = await session.execute(select(DBWorkerJob).where(DBWorkerJob.id == job_id))
            job = result.scalar_one_or_none()
            if not job:
                return False
            job.status = WorkerJobStatus.failed.value
            job.error = error
            job.updated_at = datetime.datetime.now(datetime.timezone.utc)
            await session.commit()
            return True
