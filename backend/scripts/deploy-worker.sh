#!/bin/bash
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Ensure we are in the backend directory
cd "$BACKEND_DIR"

# Configuration
JOB_NAME="worker-analysis"
REGION="us-central1"
PROJECT_ID="analyze-this-2026"

echo "Deploying $JOB_NAME to Google Cloud Run Jobs..."

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

# Deploy from source
# Note: Using :latest for secrets. In production, pinning versions is better.
gcloud run jobs deploy $JOB_NAME \
  --source . \
  --region $REGION \
  --project $PROJECT_ID \
  --command python \
  --args backend/worker_analysis.py \
  --set-env-vars "APP_ENV=production" \
  --set-secrets "FIREBASE_STORAGE_BUCKET=FIREBASE_STORAGE_BUCKET:latest" \
  --set-secrets "OPENROUTER_API_KEY=OPENROUTER_API_KEY:latest" \
  --set-secrets "OPENROUTER_MODEL=OPENROUTER_MODEL:latest"

echo "Deployment complete."
echo "You can run the job with: gcloud run jobs execute $JOB_NAME --region $REGION"
