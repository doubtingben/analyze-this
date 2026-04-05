# User Podcast Feeds Implementation Plan

**Goal:** Add per-user podcast feeds built from shared items that are eligible for audio delivery. The analysis phase should identify podcast-eligible items, enqueue a dedicated audio-generation worker, convert the item into a podcast-ready audio asset through a driver abstraction, and create/update an entry in the user’s podcast feed. Start with an ElevenLabs-backed driver.

**Architecture:** Keep podcast generation as an asynchronous extension of the existing queue-based worker pipeline. `analysis` remains responsible for understanding the item and deciding whether it belongs in the podcast feed. A new `podcast_audio` worker owns text extraction, script preparation, text-to-speech generation, and feed entry persistence. Audio generation is isolated behind a `PodcastAudioDriver` interface so ElevenLabs is the first provider, not a hard dependency spread across workers.

**Tech Stack:** Python/FastAPI, Firestore + SQLite, Cloud Run Jobs, Firebase Storage, existing worker queue framework

---

## Current State

- New shares are persisted in `shared_items` and only enqueue an `analysis` job from [backend/main.py](/home/bwilson/repos/analyze-this-codex-1/backend/main.py#L810).
- Queue processing is centralized in [backend/worker_queue.py](/home/bwilson/repos/analyze-this-codex-1/backend/worker_queue.py).
- The consolidated worker in [backend/worker.py](/home/bwilson/repos/analyze-this-codex-1/backend/worker.py) only supports `analysis`, `normalize`, and `follow_up`.
- `analysis` currently decides only between `analyzed`, `timeline`, and `follow_up` in [backend/worker_analysis.py](/home/bwilson/repos/analyze-this-codex-1/backend/worker_analysis.py).
- There is no persistence model for user podcast feeds, generated audio assets, or driver/provider metadata in [backend/models.py](/home/bwilson/repos/analyze-this-codex-1/backend/models.py) or [backend/database.py](/home/bwilson/repos/analyze-this-codex-1/backend/database.py).

This means the feature should extend the existing worker pipeline, not bypass it.

---

## Product Model

### Podcast Feed Semantics

- Each user gets a private podcast feed composed of feed entries derived from their own shared items.
- An entry represents one source item rendered as audio.
- Source items can be:
  - Already-audio uploads or links that should be included directly or normalized into the feed format.
  - Textual content that should be narrated.
  - PDFs or file-backed text documents that must first be converted into narration text.
- Feed membership is per-item and per-user. The same source item should not create duplicate entries for the same user unless explicitly regenerated as a new revision.

### Eligibility Rules

The analysis phase should classify whether an item is podcast-eligible, not generate audio directly. Initial eligibility rule set:

- Eligible by default:
  - `text`
  - `audio`
  - `file` when the file is a narratable document, starting with PDF and plain text
- Deferred for later:
  - `web_url` unless we add reliable content extraction
  - `video` unless we add transcription or audio extraction
  - `image` and `screenshot`
- The analysis result should include structured reasons when an item is not eligible so the pipeline remains explainable.

---

## Proposed Data Model

Add explicit podcast models rather than overloading `shared_items`.

### 1. Extend item analysis schema

**Files:**
- Modify: [backend/models.py](/home/bwilson/repos/analyze-this-codex-1/backend/models.py)
- Modify: [backend/analysis.py](/home/bwilson/repos/analyze-this-codex-1/backend/analysis.py)
- Modify: [backend/prompts/analyze-this.md](/home/bwilson/repos/analyze-this-codex-1/backend/prompts/analyze-this.md)

**Add to analysis payload:**

- `podcast_candidate: bool`
- `podcast_candidate_reason: str | None`
- `podcast_source_kind: str | None`
  - values: `native_audio`, `narration`, `unsupported`
- `podcast_title: str | None`
- `podcast_summary: str | None`

This keeps the “should we queue audio generation?” decision attached to the analysis result already saved on the item.

### 2. Add podcast feed entity

**Files:**
- Modify: [backend/models.py](/home/bwilson/repos/analyze-this-codex-1/backend/models.py)
- Modify: [backend/database.py](/home/bwilson/repos/analyze-this-codex-1/backend/database.py)

Add a new `PodcastFeedEntry` model with fields like:

- `id`
- `user_email`
- `item_id`
- `title`
- `summary`
- `analysis_notes`
- `shared_item_url`
- `status`
  - `queued`
  - `processing`
  - `ready`
  - `failed`
- `audio_storage_path`
- `audio_url` optional resolved URL for API output only
- `duration_seconds`
- `mime_type`
- `provider`
- `provider_voice_id`
- `source_kind`
- `script_text` or `script_excerpt`
- `error`
- `created_at`
- `updated_at`
- `published_at`

Recommendation: keep this as its own collection/table, for example `podcast_feed_entries`, because feed reads and feed regeneration are separate concerns from core item lifecycle.

`analysis_notes` should be derived from the item’s saved analysis, starting with `overview` and optionally including other human-readable fields that are useful in a podcast app’s show notes. `shared_item_url` should be a stable app/web URL back to the original shared item detail view.

### 3. Optional podcast settings entity

Not required for v1, but useful if voice/settings need to be user-specific.

- `PodcastUserSettings`
  - `user_email`
  - `feed_token`
  - `feed_enabled`
  - `voice_id`
  - `intro_template`
  - `outro_template`

For v1, `feed_token` should exist if we expose a private RSS URL.

---

## Worker Pipeline Changes

## Task 1: Teach analysis to mark podcast candidates and enqueue `podcast_audio`

**Files:**
- Modify: [backend/worker_analysis.py](/home/bwilson/repos/analyze-this-codex-1/backend/worker_analysis.py)
- Modify: [backend/analysis.py](/home/bwilson/repos/analyze-this-codex-1/backend/analysis.py)
- Modify: [backend/prompts/analyze-this.md](/home/bwilson/repos/analyze-this-codex-1/backend/prompts/analyze-this.md)

**Changes:**

1. Extend the analysis prompt and normalization so podcast-related fields are accepted and normalized.
2. After successful analysis in `_process_analysis_item`, inspect `analysis_result` and decide whether to enqueue a `podcast_audio` job.
3. Only enqueue after the item update succeeds, so the podcast worker always sees the final saved analysis.
4. Add idempotency guard:
   - either check for an existing queued/leased/ready feed entry for `(user_email, item_id)`
   - or use a deterministic job payload key and let the database layer reject duplicate queued jobs
5. Keep item status independent from podcast generation. The podcast feature should not hijack `timeline` or `follow_up` state transitions.
6. Persist enough metadata on the feed entry for episode notes:
   - `analysis_notes` from saved analysis output
   - `shared_item_url` pointing at the source item

Recommendation: do not add a new `ItemStatus` just for podcast eligibility. Treat podcast generation as an attached pipeline, not a primary lifecycle branch.

## Task 2: Add new queue job type and manager support

**Files:**
- Modify: [backend/worker.py](/home/bwilson/repos/analyze-this-codex-1/backend/worker.py)
- Modify: [backend/worker_manager.py](/home/bwilson/repos/analyze-this-codex-1/backend/worker_manager.py)
- Modify: deployment scripts under [backend/scripts](/home/bwilson/repos/analyze-this-codex-1/backend/scripts)

**Changes:**

1. Add `podcast_audio` to `JOB_TYPE_CONFIG` in `worker.py`.
2. Add a new Cloud Run Job mapping in `worker_manager.py`:
   - `"podcast_audio": "worker-podcast-audio"`
3. Update deploy scripts to support creating and deploying the new job type.
4. Reuse the existing queue processor in `worker_queue.py`; no queue framework changes should be needed beyond test coverage.

## Task 3: Create a podcast audio worker

**Files:**
- Create: `backend/worker_podcast_audio.py`

**Worker responsibilities:**

1. Fetch source item.
2. Resolve or create the corresponding `PodcastFeedEntry` in `processing` state.
3. Convert the source item into input text or source audio:
   - `text`: use item content
   - `audio`: either use source directly or normalize into stored asset metadata
   - `file` + PDF: extract text first
4. Build narration script and metadata, including episode notes and source-item link.
5. Call the configured driver.
6. Persist generated audio asset to storage.
7. Mark feed entry `ready` with storage path, duration, provider info, episode notes, source-item link, and publication timestamp.
8. On failure, mark feed entry `failed` and fail the queue job with a short actionable error code.

The worker should return `(True, None)` only after the feed entry is durable and playable.

---

## Audio Driver Design

## Task 4: Add a `PodcastAudioDriver` abstraction

**Files:**
- Create: `backend/podcast_audio.py`
- Create: `backend/podcast_drivers/__init__.py`
- Create: `backend/podcast_drivers/base.py`
- Create: `backend/podcast_drivers/elevenlabs.py`

**Interface shape:**

```python
class PodcastAudioDriver(ABC):
    async def synthesize_speech(self, *, text: str, title: str | None, voice_id: str | None, metadata: dict | None) -> AudioGenerationResult:
        ...

    async def normalize_source_audio(self, *, source_item: dict, metadata: dict | None) -> AudioGenerationResult:
        ...
```

`AudioGenerationResult` should include:

- `audio_bytes` or `storage_path`
- `mime_type`
- `duration_seconds` optional
- `provider`
- `provider_job_id` optional
- `provider_metadata`

Use a small factory like `get_podcast_audio_driver()` keyed by env var, for example `PODCAST_AUDIO_DRIVER=elevenlabs`.

## Task 5: Implement ElevenLabs as the first driver

**Files:**
- Create: `backend/podcast_drivers/elevenlabs.py`
- Modify: [backend/requirements.txt](/home/bwilson/repos/analyze-this-codex-1/backend/requirements.txt) if ElevenLabs SDK is added

**Configuration:**

- `ELEVENLABS_API_KEY`
- `ELEVENLABS_VOICE_ID`
- `ELEVENLABS_MODEL_ID` optional

**Behavior:**

- For narration, submit prepared script text to ElevenLabs TTS.
- For existing audio items, v1 can skip re-encoding and instead copy or reference the source if it is already a supported format.
- Return normalized metadata regardless of provider-specific response details.

Recommendation: keep the first version simple and synchronous from the worker’s point of view. If ElevenLabs later needs async polling, keep that complexity inside the driver.

---

## Content Preparation

## Task 6: Add content-to-audio preparation helpers

**Files:**
- Create: `backend/podcast_content.py`

**Responsibilities:**

1. `extract_podcast_text(item)`:
   - `text`: direct content
   - `file` PDF: extract text from PDF bytes
   - `audio`: return `None` because narration text is not needed
2. `build_podcast_script(item, analysis)`:
   - choose title from normalized item title, analysis `podcast_title`, or item title
   - choose summary from `podcast_summary` or `overview`
   - optionally prepend a small intro like “From your Analyze This feed”
3. `build_podcast_notes(item, analysis)`:
   - include the core analysis summary
   - include useful structured context when available, such as tags or timeline snippets
   - include a stable link back to the shared item
4. Apply guardrails:
   - max character count
   - fallback summarization for very long PDFs before TTS
   - strip obviously broken extraction output

Recommendation: script building belongs outside the driver so provider swaps do not affect product formatting.

---

## Feed Delivery

## Task 7: Add podcast feed database methods and API

**Files:**
- Modify: [backend/database.py](/home/bwilson/repos/analyze-this-codex-1/backend/database.py)
- Modify: [backend/main.py](/home/bwilson/repos/analyze-this-codex-1/backend/main.py)

**Database methods:**

- `create_or_update_podcast_feed_entry(...)`
- `get_podcast_feed_entries(user_email, limit=...)`
- `get_podcast_feed_entry_by_item(user_email, item_id)`
- `get_podcast_feed_entry(feed_entry_id, user_email)`

**API endpoints:**

- `GET /api/podcast/feed`
  - authenticated JSON view of entries and statuses
- `GET /api/podcast/rss`
  - private RSS XML for podcast apps
- `GET /api/podcast/audio/{entry_id}`
  - authenticated or tokenized media serving helper if needed

If RSS is added in v1, require a user-specific feed token. Do not expose raw predictable URLs by email alone.

### RSS structure

Each ready entry should emit:

- `guid`: stable feed entry id
- `title`
- `description`
  - populated from `analysis_notes` and ending with the shared-item link
- `pubDate`
- `enclosure` URL with byte length and mime type
- item summary and source link in the description

---

## Database Work

## Task 8: Extend Firestore and SQLite persistence

**Files:**
- Modify: [backend/database.py](/home/bwilson/repos/analyze-this-codex-1/backend/database.py)
- Modify: [backend/models.py](/home/bwilson/repos/analyze-this-codex-1/backend/models.py)

**Firestore:**

- Add a `podcast_feed_entries` collection.
- Optionally add `podcast_user_settings`.
- Add duplicate protection on `(user_email, item_id)` at the application layer, since Firestore has no unique constraint.

**SQLite:**

- Add `DBPodcastFeedEntry` table.
- Add table creation in `SQLiteDatabase.init_db()`.
- Add indexes:
  - `user_email`
  - `item_id`
  - `status`
- Use a unique index on `(user_email, item_id)` to enforce idempotency locally.

---

## Observability and Failure Handling

## Task 9: Add tracing, notifications, and retry semantics

**Files:**
- Modify: `backend/worker_podcast_audio.py`
- Modify: [backend/worker_manager.py](/home/bwilson/repos/analyze-this-codex-1/backend/worker_manager.py)
- Modify: [backend/notifications.py](/home/bwilson/repos/analyze-this-codex-1/backend/notifications.py) only if a new notification shape is needed

**Guidelines:**

- Add spans for:
  - text extraction
  - script build
  - driver call
  - storage upload
  - feed entry write
- Fail jobs with short error categories:
  - `unsupported_type`
  - `text_extraction_failed`
  - `driver_unavailable`
  - `tts_failed`
  - `storage_upload_failed`
- Allow the manager’s existing retry rule to pick up transient failures.
- Do not retry permanent unsupported-type failures indefinitely.

---

## Testing Plan

## Task 10: Add unit and integration coverage

**Files:**
- Create: `backend/tests/test_podcast_audio_driver.py`
- Create: `backend/tests/test_worker_podcast_audio.py`
- Modify: [backend/tests/test_worker_queue.py](/home/bwilson/repos/analyze-this-codex-1/backend/tests/test_worker_queue.py)
- Modify: [backend/tests/test_worker_analysis.py](/home/bwilson/repos/analyze-this-codex-1/backend/tests/test_worker_analysis.py)
- Create: `backend/tests/test_podcast_feed_api.py`

**Coverage:**

1. Analysis marks eligible text/PDF/audio items correctly.
2. Analysis enqueues `podcast_audio` only for eligible items.
3. Duplicate analysis runs do not create duplicate feed entries or duplicate queued jobs.
4. PDF/text preparation produces bounded narration script text.
5. ElevenLabs driver responses are normalized correctly.
6. Podcast worker:
   - creates ready feed entry on success
   - marks failed entry on driver failure
   - skips unsupported items safely
7. RSS/feed API only exposes the authenticated user’s entries or valid feed token scope.

---

## Rollout Order

1. Add models and database persistence for feed entries.
2. Add analysis schema updates and enqueue logic.
3. Add content-prep helpers and driver abstraction.
4. Add ElevenLabs driver.
5. Add `podcast_audio` worker and manager/deploy wiring.
6. Add JSON feed API.
7. Add RSS endpoint and feed token handling.
8. Add UI surface in web/mobile later; not required for the backend pipeline to ship.

---

## Recommended v1 Constraints

- Support only:
  - `text`
  - `audio`
  - `file` where MIME type or extension is PDF or plain text
- Do not attempt article extraction from arbitrary URLs yet.
- Do not build multi-item mixed episodes yet. One feed entry per source item is simpler and fits the current item model.
- Do not make audio generation block analysis completion.
- Do not couple podcast readiness to item `status`.

These constraints keep the feature compatible with the existing lifecycle and make provider replacement tractable.

---

## Open Questions

1. Should native audio items be copied into the feed unchanged, or should everything be normalized through the driver for consistent metadata and loudness?
2. For long PDFs, should v1 narrate full text, or produce a summarized audio brief?
3. Does the product need a real RSS feed immediately, or is an authenticated in-app feed sufficient for the first cut?
4. Should feed ordering be `shared_item.created_at` or `audio_ready_at`?
5. Do we want one global default voice, or per-user voice settings in v1?

My recommendation for v1 is: unchanged native audio when already playable, summarized narration for long PDFs, authenticated JSON feed first, order by `published_at`, and one global default ElevenLabs voice.
