import os
import datetime
import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
import logging

from models import User, SharedItem

# Firestore imports
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore import Client as FirestoreClient
from google.cloud.firestore_v1.base_query import FieldFilter

# SQLAlchemy imports
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import Column, String, DateTime, JSON, Boolean, inspect, text
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


# --- Firestore Implementation ---

class FirestoreDatabase(DatabaseInterface):
    def __init__(self):
        # Initialize Firebase if not already done
        if not firebase_admin._apps:
            firebase_admin.initialize_app(options={
                'storageBucket': os.getenv('FIREBASE_STORAGE_BUCKET')
            })
        self.db: FirestoreClient = firestore.client()

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
        self.db.collection('shared_items').add(item_dict)
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

    async def delete_shared_item(self, item_id: str, user_email: str) -> bool:
        item_ref = self.db.collection('shared_items').document(item_id)
        doc = item_ref.get()
        if not doc.exists:
            return False

        item_data = doc.to_dict()
        if item_data.get('user_email') != user_email:
            raise ValueError("Forbidden")

        item_ref.delete()
        return True

    async def get_shared_item(self, item_id: str) -> Optional[dict]:
        doc = self.db.collection('shared_items').document(item_id).get()
        if doc.exists:
            data = doc.to_dict()
            data['firestore_id'] = doc.id
            return data
        return None

    async def update_shared_item(self, item_id: str, updates: dict) -> bool:
        item_ref = self.db.collection('shared_items').document(item_id)
        # Check existence if needed, or just update
        try:
            item_ref.update(updates)
            return True
        except Exception:
            return False

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


# --- SQLite Implementation ---

Base = declarative_base()

class DBUser(Base):
    __tablename__ = 'users'
    email = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    picture = Column(String, nullable=True)
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

    async def get_user(self, email: str) -> Optional[User]:
        async with self.SessionLocal() as session:
            result = await session.execute(select(DBUser).where(DBUser.email == email))
            db_user = result.scalar_one_or_none()
            if db_user:
                return User(
                    email=db_user.email,
                    name=db_user.name,
                    picture=db_user.picture,
                    created_at=db_user.created_at
                )
            return None

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
                    created_at=user.created_at or datetime.datetime.utcnow()
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
                created_at=item.created_at or datetime.datetime.utcnow(),
                item_metadata=item.item_metadata,
                analysis=analysis_data,
                status=item.status,
                next_step=item.next_step,
                is_normalized=item.is_normalized
                hidden=item.hidden
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
                    'is_normalized': item.is_normalized
                    'hidden': item.hidden
                }
                for item in items
            ]

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
                    'is_normalized': item.is_normalized
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
                    'is_normalized': item.is_normalized
                    'hidden': item.hidden
                }
                for item in items
            ]
