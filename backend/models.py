from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class User(BaseModel):
    id: Optional[str] = Field(default=None) # Firestore ID
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SharedItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_email: str
    type: str # 'text', 'webUrl', 'media', etc.
    content: str
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    item_metadata: Optional[dict] = Field(default=None)
    analysis: Optional[dict] = Field(default=None)

