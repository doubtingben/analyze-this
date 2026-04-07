from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
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


class WorkerJobStatus(str, Enum):
    queued = 'queued'
    leased = 'leased'
    completed = 'completed'
    failed = 'failed'

class TimelineEvent(BaseModel):
    date: Optional[str] = None
    time: Optional[str] = None
    duration: Optional[str] = None
    location: Optional[str] = None
    principal: Optional[str] = None
    purpose: Optional[str] = None

class AnalysisResult(BaseModel):
    overview: str  # Required - human-readable summary for UI
    timeline: Optional[list[TimelineEvent]] = Field(default_factory=list)
    follow_up: Optional[str] = None
    tags: Optional[list[str]] = None  # Optional categorization
    podcast_candidate: bool = Field(default=False)
    podcast_candidate_reason: Optional[str] = None
    podcast_source_kind: Optional[str] = None
    podcast_title: Optional[str] = None
    podcast_summary: Optional[str] = None

class User(BaseModel):
    id: Optional[str] = Field(default=None) # Firestore ID
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    timezone: str = Field(default="America/New_York")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SharedItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_email: str
    type: ShareType
    content: str
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    item_metadata: Optional[dict] = Field(default=None)
    analysis: Optional[AnalysisResult] = Field(default=None)
    timeline: list[TimelineEvent] = Field(default_factory=list)
    status: ItemStatus = Field(default=ItemStatus.new)
    next_step: Optional[str] = Field(default=None)
    image: Optional[str] = Field(default=None)
    is_normalized: bool = Field(default=False)
    hidden: bool = Field(default=False)
    embedding: Optional[list[float]] = Field(default=None) # Vector embedding for semantic search

class NoteType(str, Enum):
    context = "context"
    follow_up = "follow_up"

class ItemNote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    item_id: str
    user_email: str
    text: Optional[str] = None
    image_path: Optional[str] = None
    note_type: str = Field(default="context")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PodcastFeedEntryStatus(str, Enum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class PodcastFeedEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    user_email: str
    item_id: str
    title: str
    summary: Optional[str] = None
    analysis_notes: Optional[str] = None
    shared_item_url: Optional[str] = None
    status: PodcastFeedEntryStatus = Field(default=PodcastFeedEntryStatus.queued)
    audio_storage_path: Optional[str] = None
    duration_seconds: Optional[int] = None
    mime_type: Optional[str] = None
    provider: Optional[str] = None
    provider_voice_id: Optional[str] = None
    source_kind: Optional[str] = None
    script_text: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    published_at: Optional[datetime] = None
