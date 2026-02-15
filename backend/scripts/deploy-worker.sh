#!/usr/bin/env bash
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
  echo "Usage: ./backend/scripts/deploy-worker.sh <manager> [region]"
  echo ""
  echo "Note: analysis, normalize, and follow_up workers are now deployed as Cloud Run Jobs."
  echo "Use ./backend/scripts/deploy-worker-job.sh to deploy them."
  exit 1
fi

JOB_TYPE="$1"
if [ "$JOB_TYPE" != "manager" ]; then
  echo "Error: This script now only deploys the manager service."
  echo "For worker jobs (analysis, normalize, follow_up), use:"
  echo "  ./backend/scripts/deploy-worker-job.sh <analysis|normalize|follow_up|all>"
  exit 1
fi

if [ -n "$2" ]; then
  REGION="$2"
fi

JOB_NAME="worker-manager"
SCRIPT_NAME="worker_manager.py"

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
check_secret "honey-comb-api-key"

LAUNCH_ARGS="$SCRIPT_NAME","--loop"

# Deploy as Cloud Run Service
# We use --no-cpu-throttling so the background loop runs even when not processing requests
# We use --min-instances 1 to keep the manager alive
gcloud run deploy $JOB_NAME \
  --source . \
  --region $REGION \
  --project $PROJECT_ID \
  --command python \
  --args "$LAUNCH_ARGS" \
  --service-account "$SERVICE_ACCOUNT_EMAIL" \
  --set-env-vars "APP_ENV=production" \
  --set-env-vars "GCP_PROJECT=${PROJECT_ID}" \
  --set-env-vars "GCP_REGION=${REGION}" \
  --set-env-vars "MANAGER_INTERVAL_SECONDS=60" \
  --set-env-vars "ENABLE_JOB_LAUNCHING=true" \
  --set-env-vars "IRCCAT_URL=https://irccat.interestedparticipant.org/send" \
  --set-env-vars "IRCCAT_ENABLED=true" \
  --set-env-vars "OTEL_ENABLED=true" \
  --set-env-vars "OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io" \
  --set-env-vars "OTEL_SERVICE_NAME=${JOB_NAME}" \
  --set-secrets "IRCCAT_BEARER_TOKEN=irc-server-password:latest" \
  --set-secrets "HONEYCOMB_API_KEY=honey-comb-api-key:latest" \
  --set-secrets "FIREBASE_STORAGE_BUCKET=FIREBASE_STORAGE_BUCKET:latest" \
  --no-cpu-throttling \
  --min-instances 1 \
  --max-instances 1 \
  --allow-unauthenticated

echo "Deployment complete."
echo "Service URL: $(gcloud run services describe $JOB_NAME --region $REGION --format 'value(status.url)')"
