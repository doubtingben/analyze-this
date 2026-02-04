# Follow-up Worker Implementation Plan

> **For Claude:** Use subagent-driven development to implement this plan task-by-task.

**Goal:** Add typed notes (context vs follow_up), a follow-up worker that re-analyzes items using follow-up notes as additional context, and UI changes to let users mark notes as follow-up responses.

**Architecture:** Add `note_type` field to notes (default `context`, optional `follow_up`). When a follow-up note is created on an item with status `follow_up`, enqueue a `follow_up` worker job. The worker fetches the item + its follow-up notes, sends them to the AI for re-analysis, and updates the item's analysis/status.

**Tech Stack:** Python/FastAPI (backend), Flutter/Dart (mobile), Vanilla JS (web), Firestore + SQLite (database)

---

## Task 1: Add NoteType enum and note_type field to models and database

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/database.py`

**Changes:**

1. Add `NoteType` enum to `models.py`:
```python
class NoteType(str, Enum):
    context = "context"
    follow_up = "follow_up"
```

2. Add `note_type` field to `ItemNote` model:
```python
class ItemNote(BaseModel):
    ...
    note_type: str = "context"  # Use string for flexibility, values: "context", "follow_up"
```

3. Update `FirestoreDatabase.create_item_note()` to include `note_type` in the stored dict:
```python
note_dict = {
    ...
    'note_type': note.note_type,
}
```

4. Update `FirestoreDatabase.get_item_notes()` to include `note_type` in returned dicts.

5. Update `DBItemNote` SQLAlchemy model to add `note_type` column:
```python
note_type = Column(String, default='context')
```

6. Add migration in `SQLiteDatabase.init_db()` to add `note_type` column to existing `item_notes` tables:
```python
def ensure_note_type_column(sync_conn):
    inspector = inspect(sync_conn)
    columns = [col['name'] for col in inspector.get_columns('item_notes')]
    if 'note_type' not in columns:
        sync_conn.execute(text("ALTER TABLE item_notes ADD COLUMN note_type VARCHAR DEFAULT 'context'"))
```

7. Update `SQLiteDatabase.create_item_note()` to include `note_type`.

8. Update `SQLiteDatabase.get_item_notes()` to include `note_type` in returned dicts.

9. Add new database method `get_follow_up_notes(item_id)` to both Firestore and SQLite implementations - returns only notes with `note_type='follow_up'` for a given item. Add to abstract interface too.

---

## Task 2: Update API to accept note_type and enqueue follow_up jobs

**Files:**
- Modify: `backend/main.py`

**Changes:**

1. Update `POST /api/items/{item_id}/notes` endpoint to accept `note_type` form field:
```python
async def create_item_note(
    item_id: str,
    request: Request,
    text: str = Form(None),
    file: UploadFile = File(None),
    note_type: str = Form("context")
):
```

2. Validate `note_type` is either "context" or "follow_up".

3. Pass `note_type` to the `ItemNote` constructor.

4. Include `note_type` in the response data dict.

5. After creating a follow_up note, check if the item has `status == 'follow_up'` and if so, enqueue a `follow_up` worker job:
```python
if note_type == "follow_up" and item.get('status') == 'follow_up':
    try:
        await db.enqueue_worker_job(item_id, user_email, "follow_up", {"source": "note"})
    except Exception as e:
        print(f"Failed to enqueue follow_up job: {e}")
```

6. Update `GET /api/items/{item_id}/notes` to include `note_type` in the response (it should already flow through from the database layer changes in Task 1).

---

## Task 3: Create follow-up prompt and analysis module

**Files:**
- Create: `backend/prompts/follow-up.md`
- Create: `backend/follow_up_analysis.py`

**Prompt (`prompts/follow-up.md`):**

Boilerplate prompt that instructs the AI to re-analyze an item given the original content, original analysis, and follow-up notes. Output format matches the existing `AnalysisResult` schema (overview, timeline, follow_up, tags).

**Analysis module (`follow_up_analysis.py`):**

A function `analyze_follow_up(content, item_type, original_analysis, follow_up_notes, preferred_tags)` that:
- Loads the follow-up prompt from `prompts/follow-up.md`
- Builds the messages array with the system prompt, original content, original analysis, and follow-up notes
- Calls OpenRouter and parses the JSON response
- Uses the same `normalize_analysis()` from `analysis.py`
- Returns the analysis result dict

Pattern follows `analysis.py` closely - uses same OpenRouter client setup, same `normalize_analysis`, same error handling.

---

## Task 4: Create follow-up worker

**Files:**
- Create: `backend/worker_follow_up.py`

**Implementation:**

Follow the pattern of `worker_analysis.py`:
- `get_db()` helper (or import from worker_analysis)
- `_process_follow_up_item(db, data, context)` function:
  1. Get item_id from data
  2. Fetch the item via `db.get_shared_item(item_id)`
  3. Verify item has status `follow_up` and `analysis.follow_up` is set
  4. Fetch follow-up notes via `db.get_follow_up_notes(item_id)`
  5. If no follow-up notes, return failure (no notes to process)
  6. Call `analyze_follow_up()` with item content, type, original analysis, notes, and preferred tags
  7. Determine new status from result (timeline/analyzed/follow_up)
  8. Update item with new analysis and status
  9. Return (True, None) on success, (False, error) on failure

- `main()` with argparse supporting `--queue`, `--loop`, `--lease-seconds`, `--limit`, `--id`
- Queue mode uses `process_queue_jobs()` with `job_type="follow_up"`
- `prepare_fn` loads preferred tags per user (same as worker_analysis)

---

## Task 5: Update deploy script for follow_up worker

**Files:**
- Modify: `backend/scripts/deploy-worker.sh`

**Changes:**

1. Add `follow_up` to the valid job types check:
```bash
if [ "$JOB_TYPE" != "analysis" ] && [ "$JOB_TYPE" != "normalize" ] && [ "$JOB_TYPE" != "manager" ] && [ "$JOB_TYPE" != "follow_up" ]; then
  echo "Error: job type must be 'analysis', 'normalize', 'manager', or 'follow_up'."
  exit 1
fi
```

2. The follow_up worker needs OpenRouter keys (same as analysis/normalize), so it falls into the `else` branch with `LAUNCH_ARGS="$SCRIPT_NAME","--queue","--loop"`.

---

## Task 6: Flutter UI - Add follow-up checkbox to note creation

**Files:**
- Modify: `flutter/lib/models/item_note.dart`
- Modify: `flutter/lib/services/api_service.dart`
- Modify: `flutter/lib/screens/item_detail_screen.dart`

**Model changes (`item_note.dart`):**
- Add `noteType` field (String, default 'context') to `ItemNote`
- Update `fromJson`, `toJson`, `copyWith`

**API service changes (`api_service.dart`):**
- Add `noteType` parameter to `createNote()` method
- Include `note_type` field in the multipart form request

**UI changes (`item_detail_screen.dart`):**

1. Add `_isFollowUp` boolean state to `_AddNoteBottomSheetState`

2. Add a checkbox/switch row below the text field:
```dart
CheckboxListTile(
  value: _isFollowUp,
  onChanged: (v) => setState(() => _isFollowUp = v ?? false),
  title: const Text('Follow-up response'),
  controlAffinity: ListTileControlAffinity.leading,
  contentPadding: EdgeInsets.zero,
)
```

3. Return `noteType` in the result map from the bottom sheet:
```dart
Navigator.of(context).pop({
  'text': text.isNotEmpty ? text : null,
  'imagePath': _selectedImagePath,
  'noteType': _isFollowUp ? 'follow_up' : 'context',
});
```

4. Update `_createNote` in `ItemDetailScreen` to pass `noteType` to `ApiService.createNote()`

5. In note rendering, show a small visual indicator for follow-up notes (e.g., a flag icon or "Follow-up" label)

---

## Task 7: Web UI - Add follow-up checkbox to note creation

**Files:**
- Modify: `backend/static/index.html`
- Modify: `backend/static/app.js`
- Modify: `backend/static/styles.css`

**HTML changes (`index.html`):**
Add a checkbox row inside the note form, before the submit button:
```html
<form id="detail-note-form" class="detail-note-form">
    <textarea id="detail-note-text" rows="3" placeholder="Add a note..."></textarea>
    <label class="note-type-toggle">
        <input type="checkbox" id="detail-note-follow-up" />
        <span>Follow-up response</span>
    </label>
    <button class="btn-primary" type="submit">Add note</button>
</form>
```

**JS changes (`app.js`):**

1. Get reference to the checkbox element.

2. In the note form submit handler, read the checkbox value and append `note_type` to the FormData:
```javascript
const isFollowUp = detailNoteFollowUp.checked;
formData.append('note_type', isFollowUp ? 'follow_up' : 'context');
```

3. After successful submission, reset the checkbox.

4. In `renderDetailNotes()`, show a visual indicator for follow-up notes (e.g., a small badge or label).

**CSS changes (`styles.css`):**
- Style `.note-type-toggle` - inline flex row with checkbox and label
- Style `.note-type-badge` - small indicator on follow-up notes

---

## Verification

**Syntax check:**
```bash
cd backend && python3 -c "import ast; ast.parse(open('worker_follow_up.py').read()); print('OK')"
cd backend && python3 -c "import ast; ast.parse(open('follow_up_analysis.py').read()); print('OK')"
cd backend && python3 -c "import ast; ast.parse(open('models.py').read()); print('OK')"
cd backend && python3 -c "import ast; ast.parse(open('database.py').read()); print('OK')"
cd backend && python3 -c "import ast; ast.parse(open('main.py').read()); print('OK')"
```

**Flutter analyze:**
```bash
cd flutter && flutter analyze
```
