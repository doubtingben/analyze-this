#!/bin/bash
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Ensure we are in the backend directory
cd "$BACKEND_DIR"

# Configuration
SERVICE_NAME="analyze-this-backend"
REGION="us-central1"

PROJECT_ID="analyze-this-2026"

echo "Deploying $SERVICE_NAME to Google Cloud Run..."

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
check_secret "SECRET_KEY"
check_secret "GOOGLE_CLIENT_ID"
check_secret "GOOGLE_CLIENT_SECRET"
check_secret "FIREBASE_STORAGE_BUCKET"
check_secret "GOOGLE_EXTENSION_CLIENT_ID"

# Generate version file
GIT_HASH=$(git rev-parse HEAD)
echo "$GIT_HASH" > version.txt
echo "Version set to: $GIT_HASH"

# Deploy from source (requires Cloud Build api enabled)
# Ensure we are in the backend directory
cd "$BACKEND_DIR"

gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --set-env-vars "^@^ALLOWED_ORIGINS=https://interestedparticipant.org,chrome-extension://ilbniloahihehnhalvffoelaliheab" \
  --set-secrets "SECRET_KEY=SECRET_KEY:latest" \
  --set-secrets "GOOGLE_CLIENT_ID=GOOGLE_CLIENT_ID:latest" \
  --set-secrets "GOOGLE_CLIENT_SECRET=GOOGLE_CLIENT_SECRET:latest" \
  --set-secrets "FIREBASE_STORAGE_BUCKET=FIREBASE_STORAGE_BUCKET:latest" \
  --set-secrets "GOOGLE_EXTENSION_CLIENT_ID=GOOGLE_EXTENSION_CLIENT_ID:latest"

# Cleanup
rm version.txt

echo "Deployment complete."
