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

if [ -z "$1" ]; then
  echo "Usage: ./backend/scripts/deploy-worker-job.sh <analysis|normalize|follow_up|all> [region]"
  exit 1
fi

if [ -n "$2" ]; then
  REGION="$2"
fi

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

deploy_worker_job() {
    local JOB_TYPE="$1"
    local JOB_NAME="worker-${JOB_TYPE//_/-}"

    echo "Deploying Cloud Run Job: $JOB_NAME (job_type=$JOB_TYPE)..."

    gcloud run jobs deploy "$JOB_NAME" \
      --source . \
      --region "$REGION" \
      --project "$PROJECT_ID" \
      --command python \
      --args "worker.py,--job-type,${JOB_TYPE},--limit,20" \
      --service-account "$SERVICE_ACCOUNT_EMAIL" \
      --set-env-vars "APP_ENV=production" \
      --set-env-vars "IRCCAT_URL=https://irccat.interestedparticipant.org/send" \
      --set-env-vars "IRCCAT_ENABLED=true" \
      --set-env-vars "OTEL_ENABLED=true" \
      --set-env-vars "OTEL_EXPORTER_OTLP_ENDPOINT=https://api.honeycomb.io" \
      --set-env-vars "OTEL_SERVICE_NAME=${JOB_NAME}" \
      --set-secrets "IRCCAT_BEARER_TOKEN=irc-server-password:latest" \
      --set-secrets "HONEYCOMB_API_KEY=honey-comb-api-key:latest" \
      --set-secrets "FIREBASE_STORAGE_BUCKET=FIREBASE_STORAGE_BUCKET:latest" \
      --set-secrets "OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest" \
      --set-secrets "OPENROUTER_MODEL=OPENROUTER_MODEL:latest" \
      --task-timeout 900 \
      --max-retries 0

    echo "Cloud Run Job '$JOB_NAME' deployed successfully."
}

# Verify required secrets
echo "Verifying required secrets in Secret Manager..."
check_secret "FIREBASE_STORAGE_BUCKET"
check_secret "OPENROUTER_API_KEY"
check_secret "OPENROUTER_MODEL"
check_secret "irc-server-password"
check_secret "honey-comb-api-key"

JOB_TYPE="$1"

if [ "$JOB_TYPE" = "all" ]; then
    deploy_worker_job "analysis"
    deploy_worker_job "normalize"
    deploy_worker_job "follow_up"
elif [ "$JOB_TYPE" = "analysis" ] || [ "$JOB_TYPE" = "normalize" ] || [ "$JOB_TYPE" = "follow_up" ]; then
    deploy_worker_job "$JOB_TYPE"
else
    echo "Error: job type must be 'analysis', 'normalize', 'follow_up', or 'all'."
    exit 1
fi

echo "Deployment complete."
