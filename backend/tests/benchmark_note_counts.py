import sys
import os
import time
import asyncio
import unittest
from uuid import uuid4

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import SQLiteDatabase
from models import SharedItem

class BenchmarkNoteCounts(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db_path = f"./test_perf_{uuid4()}.db"
        self.db = SQLiteDatabase(f"sqlite+aiosqlite:///{self.db_path}")
        await self.db.init_db()

        self.user_email = "perf@example.com"
        self.num_items = 2000
        self.item_ids = []

        print(f"Seeding {self.num_items} items...")
        for i in range(self.num_items):
            item_id = str(uuid4())
            item = SharedItem(
                id=item_id,
                user_email=self.user_email,
                title=f"Item {i}",
                content=f"Content {i}",
                type="text"
            )
            await self.db.create_shared_item(item)
            if i < 10:
                self.item_ids.append(item_id)
        print("Seeding complete.")

    async def asyncTearDown(self):
        await self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    async def test_performance_current_logic(self):
        # Emulate the current logic in main.py
        start_time = time.time()

        # 1. Get all user items
        user_items = await self.db.get_shared_items(self.user_email)
        # 2. Extract IDs
        user_item_ids = {item.get('firestore_id') for item in user_items}
        # 3. Intersect
        requested_item_ids = self.item_ids
        authorized_item_ids = [item_id for item_id in requested_item_ids if item_id in user_item_ids]

        # 4. Get counts (simulated)
        counts = await self.db.get_item_note_count(authorized_item_ids)

        end_time = time.time()
        duration = end_time - start_time
        print(f"Current logic took: {duration:.4f}s for {self.num_items} items")

    async def test_performance_optimized_logic_preview(self):
        # Emulate the optimized logic
        # We need to implement validate_user_item_ownership first or just inline it here for the preview
        start_time = time.time()

        # Optimized: query only specific IDs for the user
        async with self.db.SessionLocal() as session:
            from sqlalchemy.future import select
            from database import DBSharedItem
            result = await session.execute(
                select(DBSharedItem.id)
                .where(DBSharedItem.user_email == self.user_email)
                .where(DBSharedItem.id.in_(self.item_ids))
            )
            authorized_item_ids = [row[0] for row in result.all()]

        # Get counts
        counts = await self.db.get_item_note_count(authorized_item_ids)

        end_time = time.time()
        duration = end_time - start_time
        print(f"Optimized logic took: {duration:.4f}s for {self.num_items} items")

if __name__ == '__main__':
    unittest.main()
