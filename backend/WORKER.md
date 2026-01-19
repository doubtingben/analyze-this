# Analysis Worker

This worker script is responsible for processing `SharedItem`s in the database that have not yet been analyzed by the AI.

## Overview
The worker connects to Firestore, queries for items where `analysis` is `null`, sends the content to the AI model, and updates the document with the result.

## Usage

### Prerequisites
- Python 3.9+ installed
- Dependencies installed (`pip install -r requirements.txt`)
- Environment variables configured (see below)

### Running the Worker

**Process next batch (default 10):**
```bash
python backend/worker_analysis.py
```

**Process N items:**
```bash
python backend/worker_analysis.py --limit 50
```

**Process a specific item:**
```bash
python backend/worker_analysis.py --id <firestore_document_id>
```

**Force re-analyze a specific item:**
```bash
python backend/worker_analysis.py --id <firestore_document_id> --force
```

## Environment Variables

The worker uses the same `.env` file as the backend. Ensure these are set:

| Variable | Description |
|bound|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON (not needed if running in Cloud Run) |
| `FIREBASE_STORAGE_BUCKET` | The name of the GCS bucket for Firebase Storage |
| `OPENROUTER_API_KEY` | API Key for OpenRouter (AI Model) |
| `OPENROUTER_MODEL` | (Optional) Model identifier, defaults to `google/gemini-2.0-flash-exp:free` |

## Deployment logic
For production, this script can be run as a Job (Cloud Run Job) on a schedule (e.g., every minute) or triggered via Eventarc when a new document is created in Firestore (requires wrapping in a Cloud Function or Cloud Run service wrapper).
