# Analysis + Normalize Workers

These worker scripts process `SharedItem`s using a Firestore-backed queue.

## Overview
New items enqueue two jobs: `analysis` and `normalize`. Cloud Run Jobs run the worker scripts, which lease queued jobs, process the item, and mark the job complete.

## Usage

### Prerequisites
- Python 3.9+ installed
- Dependencies installed (`pip install -r requirements.txt`)
- Environment variables configured (see below)

### Running the Worker

**Process next batch from the queue (default 10):**
```bash
python backend/worker_analysis.py --queue
```

**Process N queued jobs:**
```bash
python backend/worker_analysis.py --queue --limit 50
```

**Process a specific item (legacy mode):**
```bash
python backend/worker_analysis.py --id <firestore_document_id>
```

**Force re-analyze a specific item (legacy mode):**
```bash
python backend/worker_analysis.py --id <firestore_document_id> --force
```

## Normalize Worker (Queue Mode)

```bash
python backend/worker_normalize.py --queue
```

## Environment Variables / Secrets

The worker uses the same `.env` file as the backend. Ensure these are set:

| Variable | Description |
|bound|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON (not needed if running in Cloud Run) |
| `FIREBASE_STORAGE_BUCKET` | The name of the GCS bucket for Firebase Storage |
| `OPENROUTER_API_KEY` | API Key for OpenRouter (AI Model) |
| `OPENROUTER_MODEL` | (Optional) Model identifier, defaults to `google/gemini-2.0-flash-exp:free` |

## Required IAM Permissions

For the Cloud Run Job service account:
- `roles/datastore.user` (Firestore read/write)
- `roles/storage.objectViewer` (read uploaded files for analysis)
- `roles/secretmanager.secretAccessor` (read secrets)

If you plan to trigger Cloud Run Jobs programmatically (dispatcher/scheduler service):
- `roles/run.developer` or `roles/run.admin`
- `roles/iam.serviceAccountUser` (to run jobs as the worker SA)

## Deployment logic
For production, run Cloud Run Jobs on a schedule (e.g., every minute) or via Eventarc. The job processes queued work items.

### Deploy jobs
Use the unified deploy script:
```bash
./backend/scripts/deploy-worker.sh analysis
./backend/scripts/deploy-worker.sh normalize
```
