from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field

class ShareType(str, Enum):
    text = 'text'
    web_url = 'web_url'
    weburl = 'weburl'
    media = 'media'
    image = 'image'
    video = 'video'
    audio = 'audio'
    file = 'file'
    screenshot = 'screenshot'

class ItemStatus(str, Enum):
    new = 'new'
    analyzing = 'analyzing'
    analyzed = 'analyzed'
    timeline = 'timeline'
    follow_up = 'follow_up'
    processed = 'processed'
    soft_deleted = 'soft_deleted'

class TimelineEvent(BaseModel):
    date: Optional[str] = None
    time: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    principal: Optional[str] = None

class AnalysisResult(BaseModel):
    overview: str  # Required - human-readable summary for UI
    timeline: Optional[TimelineEvent] = None
    follow_up: Optional[str] = None
    tags: Optional[list[str]] = None  # Optional categorization

class User(BaseModel):
    id: Optional[str] = Field(default=None) # Firestore ID
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SharedItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_email: str
    type: ShareType
    content: str
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    item_metadata: Optional[dict] = Field(default=None)
    analysis: Optional[AnalysisResult] = Field(default=None)
    status: ItemStatus = Field(default=ItemStatus.new)
    next_step: Optional[str] = Field(default=None)
    is_normalized: bool = Field(default=False)
    hidden: bool = Field(default=False)
