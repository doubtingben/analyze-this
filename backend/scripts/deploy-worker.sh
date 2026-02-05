#!/bin/bash
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Ensure we are in the backend directory
cd "$BACKEND_DIR"

# Configuration
REGION="us-central1"
PROJECT_ID="analyze-this-2026"

# Service Account Configuration
SERVICE_ACCOUNT_NAME="worker-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Using Service Account: $SERVICE_ACCOUNT_EMAIL"
echo "Note: Ensure this service account is created and has 'Secret Manager Secret Accessor' role."
echo "Run './backend/scripts/setup-worker-sa.sh' to configure it if needed."

if [ -z "$1" ]; then
  echo "Usage: ./backend/scripts/deploy-worker.sh <analysis|normalize|manager|follow_up> [region]"
  exit 1
fi

JOB_TYPE="$1"
if [ "$JOB_TYPE" != "analysis" ] && [ "$JOB_TYPE" != "normalize" ] && [ "$JOB_TYPE" != "manager" ] && [ "$JOB_TYPE" != "follow_up" ]; then
  echo "Error: job type must be 'analysis', 'normalize', 'manager', or 'follow_up'."
  exit 1
fi

if [ -n "$2" ]; then
  REGION="$2"
fi

JOB_NAME="worker-${JOB_TYPE//_/-}"
SCRIPT_NAME="worker_${JOB_TYPE}.py"

echo "Deploying $JOB_NAME to Google Cloud Run (Service)..."

# Helper function to check if secret exists
check_secret() {
    local SECRET_NAME=$1

    if ! gcloud secrets describe "$SECRET_NAME" --project "$PROJECT_ID" > /dev/null 2>&1; then
        echo "Error: Secret '$SECRET_NAME' does not exist in project '$PROJECT_ID'."
        echo "Please create it using: printf 'YOUR_SECRET' | gcloud secrets create $SECRET_NAME --data-file=-"
        exit 1
    else
        echo "Secret '$SECRET_NAME' verified."
    fi
}

echo "Verifying required secrets in Secret Manager..."
check_secret "FIREBASE_STORAGE_BUCKET"
check_secret "OPENROUTER_API_KEY"
check_secret "OPENROUTER_MODEL"
check_secret "irc-server-password"

# Build deploy command args based on job type
if [ "$JOB_TYPE" = "manager" ]; then
  # Manager only needs Firestore access, not OpenRouter
  LAUNCH_ARGS="$SCRIPT_NAME","--loop"
  SECRETS_FLAGS="--set-secrets=FIREBASE_STORAGE_BUCKET=FIREBASE_STORAGE_BUCKET:latest"
else
  # Analysis and normalize workers need OpenRouter
  check_secret "OPENROUTER_API_KEY"
  check_secret "OPENROUTER_MODEL"
  LAUNCH_ARGS="$SCRIPT_NAME","--queue","--loop"
  SECRETS_FLAGS="--set-secrets=FIREBASE_STORAGE_BUCKET=FIREBASE_STORAGE_BUCKET:latest --set-secrets=OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest --set-secrets=OPENROUTER_MODEL=OPENROUTER_MODEL:latest"
fi

# Deploy as Cloud Run Service
# We use --no-cpu-throttling so the background loop runs even when not processing requests
# We use --min-instances 1 to keep at least one worker alive
gcloud run deploy $JOB_NAME \
  --source . \
  --region $REGION \
  --project $PROJECT_ID \
  --command python \
  --args "$LAUNCH_ARGS" \
  --service-account "$SERVICE_ACCOUNT_EMAIL" \
  --set-env-vars "APP_ENV=production" \
  --set-env-vars "IRCCAT_URL=https://chat.interestedparticipant.org/send" \
  --set-env-vars "IRCCAT_ENABLED=true" \
  --set-secrets "IRCCAT_BEARER_TOKEN=irc-server-password:latest" \
  --set-secrets "FIREBASE_STORAGE_BUCKET=FIREBASE_STORAGE_BUCKET:latest" \
  --set-secrets "OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest" \
  --set-secrets "OPENROUTER_MODEL=OPENROUTER_MODEL:latest" \
  --no-cpu-throttling \
  --min-instances 1 \
  --max-instances 1 \
  --allow-unauthenticated

echo "Deployment complete."
echo "Service URL: $(gcloud run services describe $JOB_NAME --region $REGION --format 'value(status.url)')"
