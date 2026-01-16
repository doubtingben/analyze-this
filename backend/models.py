from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel, JSON

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True)
    name: Optional[str] = None
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SharedItem(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_email: str = Field(index=True)
    type: str # 'text', 'webUrl', 'media', etc.
    content: str
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    item_metadata: Optional[dict] = Field(default=None, sa_type=JSON)
