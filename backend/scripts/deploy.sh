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

echo "Deploying $SERVICE_NAME to Google Cloud Run..."

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
  --project analyze-this-2026 \
  --allow-unauthenticated \
  --update-env-vars "GOOGLE_EXTENSION_CLIENT_ID=${GOOGLE_EXTENSION_CLIENT_ID}"

# Cleanup
rm version.txt

echo "Deployment complete."
