#!/bin/bash
set -e

# Configuration
SERVICE_NAME="analyze-this-backend"
REGION="us-central1"

echo "Deploying $SERVICE_NAME to Google Cloud Run..."

# Deploy from source (requires Cloud Build api enabled)
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --project analyze-this-2026 \
  --allow-unauthenticated \
  --update-env-vars "GOOGLE_EXTENSION_CLIENT_ID=${GOOGLE_EXTENSION_CLIENT_ID}"

echo "Deployment complete."
