#!/usr/bin/env bash
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
PROJECT_ID="analyze-this-2026"
SERVICE_ACCOUNT_NAME="worker-sa"
SERVICE_ACCOUNT_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Setting up Service Account for project: $PROJECT_ID"

# 1. Create Service Account
echo "Checking for service account $SERVICE_ACCOUNT_EMAIL..."
if ! gcloud iam service-accounts describe "$SERVICE_ACCOUNT_EMAIL" --project "$PROJECT_ID" > /dev/null 2>&1; then
    echo "Creating service account $SERVICE_ACCOUNT_NAME..."
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --display-name "Worker Service Account" \
        --project "$PROJECT_ID"
else
    echo "Service account $SERVICE_ACCOUNT_EMAIL already exists."
fi

# 2. Grant Permissions
echo "Granting Secret Manager Secret Accessor role..."
# Note: This binding is project-wide. 
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role "roles/secretmanager.secretAccessor" \
    --condition None > /dev/null

echo "Granting Firestore (Datastore) user role..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role "roles/datastore.user" \
    --condition None > /dev/null

echo "Granting Storage Object Viewer role..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role "roles/storage.objectViewer" \
    --condition None > /dev/null

echo "Granting Cloud Run Developer role (to execute Cloud Run Jobs)..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role "roles/run.developer" \
    --condition None > /dev/null

echo "Granting Service Account User role (to run jobs as the service account)..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member "serviceAccount:$SERVICE_ACCOUNT_EMAIL" \
    --role "roles/iam.serviceAccountUser" \
    --condition None > /dev/null

echo "Service Account setup complete."
