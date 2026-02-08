# Honeycomb Tracing Setup

This guide explains how to configure OpenTelemetry tracing to send traces to Honeycomb.

## Prerequisites

- A Honeycomb account (sign up at https://www.honeycomb.io)
- The backend service running with the OpenTelemetry dependencies installed

## Environment Variables

Set the following environment variables to enable tracing:

```bash
# Required: Enable tracing and set Honeycomb endpoint
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io
OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=YOUR_API_KEY

# Optional: Customize service name (defaults to "analyzethis-api")
OTEL_SERVICE_NAME=analyzethis-api
```

## Getting Your Honeycomb API Key

1. Log in to your Honeycomb account at https://ui.honeycomb.io
2. Go to **Settings** (gear icon) > **API Keys**
3. Click **Create API Key**
4. Give it a name (e.g., "AnalyzeThis API")
5. Select permissions: **Send Events** is sufficient for tracing
6. Copy the generated key

## Local Development Setup

Create a `.env` file in the `backend/` directory:

```bash
# .env
OTEL_ENABLED=true
OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io
OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=your-api-key-here
OTEL_SERVICE_NAME=analyzethis-api-dev
```

Then start the backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

## Production Deployment (Cloud Run)

Add the environment variables to your Cloud Run service:

```bash
gcloud run services update analyzethis-api \
  --set-env-vars="OTEL_ENABLED=true" \
  --set-env-vars="OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io" \
  --set-env-vars="OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=YOUR_API_KEY" \
  --set-env-vars="OTEL_SERVICE_NAME=analyzethis-api"
```

Or use Google Secret Manager for the API key:

```bash
# Create secret
echo -n "your-api-key" | gcloud secrets create honeycomb-api-key --data-file=-

# Reference in Cloud Run
gcloud run services update analyzethis-api \
  --set-secrets="HONEYCOMB_API_KEY=honeycomb-api-key:latest"
```

Then set `OTEL_EXPORTER_OTLP_HEADERS=x-honeycomb-team=${HONEYCOMB_API_KEY}` in your deployment config.

## What Gets Traced

With the current implementation, the following operations are traced:

### Notes API (`POST /api/items/{item_id}/notes`)

- **Root span**: The entire request with attributes:
  - `note.item_id`: The item ID the note is attached to
  - `note.type`: Either "context" or "follow_up"
  - `note.has_file`: Whether a file was uploaded
  - `note.has_text`: Whether text was provided
  - `user.email`: The authenticated user
  - `note.id`: The created note ID

- **Child spans**:
  - `authenticate_user`: User authentication check
  - `lookup_item`: Database lookup for the parent item
  - `upload_file`: File upload to storage (if applicable)
  - `create_note_db`: Database insert for the note
  - `enqueue_follow_up_job`: Worker job enqueue (for follow_up notes)

### Distributed Tracing: Follow-up Worker

When a follow_up note is created, the trace context is propagated to the worker queue. The follow-up worker creates a **linked trace** that references the original API request.

**Worker spans** (`worker.follow_up`):
- `job.id`: The worker job ID
- `job.type`: "follow_up"
- `job.item_id`: The item being processed
- `worker.id`: The worker instance ID
- `linked.trace_id`: Reference to the original API trace
- `linked.span_id`: Reference to the enqueue span

**Child spans in worker**:
- `fetch_item`: Fetches the shared item from database
- `process_item`: Wrapper around the processing function
  - `fetch_item_for_follow_up`: Re-fetches item with full data
  - `fetch_follow_up_notes`: Fetches notes for the item
  - `llm_follow_up_analysis`: Wrapper around LLM call
    - `openrouter_api_call`: The actual LLM API call with:
      - `llm.provider`: "openrouter"
      - `llm.model`: The model used
      - `llm.prompt_tokens`, `llm.completion_tokens`, `llm.total_tokens`
      - `llm.action`: The action returned (delete/archive/update)
  - `execute_action_*`: The action taken (delete/archive/update)

### FastAPI Automatic Instrumentation

All HTTP requests are automatically traced with:
- HTTP method, path, status code
- Request/response timing
- Error details on failures

## Viewing Traces in Honeycomb

1. Go to https://ui.honeycomb.io
2. Select your dataset (it will be named after your service)
3. Use the Query Builder to explore:
   - **Trace waterfall**: Click on any trace to see the span hierarchy
   - **Latency distribution**: Use `HEATMAP(duration_ms)` grouped by `name`
   - **Error rate**: Filter by `error = true` or `status_code >= 400`

### Useful Queries

**Average latency by operation:**
```
HEATMAP(duration_ms) GROUP BY name WHERE service.name = "analyzethis-api"
```

**Error traces:**
```
WHERE error = true OR http.status_code >= 400
```

**Slow note creation:**
```
WHERE name = "POST /api/items/{item_id}/notes" AND duration_ms > 1000
```

**File upload performance:**
```
WHERE name = "upload_file" HEATMAP(duration_ms) GROUP BY file.storage_type
```

**Follow-up worker jobs:**
```
WHERE name = "worker.follow_up" HEATMAP(duration_ms) GROUP BY job.status
```

**LLM API call latency:**
```
WHERE name = "openrouter_api_call" HEATMAP(duration_ms) GROUP BY llm.model
```

**LLM token usage:**
```
WHERE name = "openrouter_api_call" AVG(llm.total_tokens) GROUP BY llm.model
```

**Trace a note from creation to worker processing:**
```
WHERE linked.trace_id = "<trace_id_from_note_creation>"
```

**Failed worker jobs:**
```
WHERE name = "worker.follow_up" AND job.status = "failed"
```

## Disabling Tracing

To disable tracing without code changes:

```bash
OTEL_ENABLED=false
```

Or simply don't set `OTEL_EXPORTER_OTLP_ENDPOINT`.

## Troubleshooting

### No traces appearing

1. Check that `OTEL_ENABLED=true`
2. Verify `OTEL_EXPORTER_OTLP_ENDPOINT` is set to `https://api.honeycomb.io`
3. Confirm your API key is correct in `OTEL_EXPORTER_OTLP_HEADERS`
4. Check backend logs for tracing initialization messages

### "OpenTelemetry tracing disabled" in logs

This means one of the required environment variables is missing. Check:
- `OTEL_EXPORTER_OTLP_ENDPOINT` is set
- API key header is properly formatted

### Traces appear but missing spans

Child spans may not appear if:
- The operation completed too quickly (< 1ms)
- An exception was raised before the span completed
- The tracer wasn't properly initialized

Check that `init_tracing()` runs successfully in the lifespan.
