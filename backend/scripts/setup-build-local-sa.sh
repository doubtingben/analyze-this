#!/usr/bin/env bash
set -e

# Configuration
PROJECT_ID="analyze-this-2026"
SERVICE_ACCOUNT_NAME="build-local"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Setting up Build/Deploy Service Account: $SERVICE_ACCOUNT_EMAIL"

# 1. Create Service Account
if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --project "$PROJECT_ID" > /dev/null 2>&1; then
    echo "Creating service account $SERVICE_ACCOUNT_NAME..."
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --display-name "Build Local Service Account" \
        --project "$PROJECT_ID"
else
    echo "Service account $SERVICE_ACCOUNT_EMAIL already exists."
fi

# 2. Grant Permissions
# Roles required for 'gcloud run deploy --source .'
ROLES=(
    "roles/run.admin"                # Create/Update Cloud Run services
    "roles/iam.serviceAccountUser"   # Act as the runtime service account
    "roles/cloudbuild.builds.editor" # Trigger Cloud Build for the deployment
    "roles/artifactregistry.writer"  # Push images to Artifact Registry
    "roles/secretmanager.viewer"     # Verify secrets exist (required by deploy.sh)
    "roles/storage.objectAdmin"      # Upload source code to storage for Cloud Build
    "roles/storage.admin"      # Get the build-artifacts bucket
    "roles/serviceusage.serviceUsageConsumer" # Enable APIs
)

for role in "${ROLES[@]}"; do
    echo "Granting $role..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member "serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
        --role "$role" \
        --condition None > /dev/null
done

echo "Setup complete."
