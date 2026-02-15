#!/usr/bin/env bash
set -e

# Configuration
PROJECT_ID="analyze-this-2026" # Ensure this matches your project ID
BUILD_SA_NAME="cloud-build-sa"
BUILD_SA_EMAIL="$BUILD_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
RUNTIME_SA_NAME="backend-runtime-sa"
RUNTIME_SA_EMAIL="$RUNTIME_SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
GITHUB_REPO_OWNER="doubtingben" # Replace with your GitHub owner
GITHUB_REPO_NAME="analyze-this"  # Replace with your GitHub repo name

echo "Setting up GCP Pipeline for project: $PROJECT_ID"

# 1. Enable APIs
echo "Enabling necessary APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    secretmanager.googleapis.com \
    iam.googleapis.com \
    --project "$PROJECT_ID"

# 2. Create Cloud Build Service Account
echo "Creating Cloud Build Service Account..."
if ! gcloud iam service-accounts describe "$BUILD_SA_EMAIL" --project "$PROJECT_ID" > /dev/null 2>&1; then
    gcloud iam service-accounts create "$BUILD_SA_NAME" \
        --display-name="Cloud Build Service Account" \
        --project "$PROJECT_ID"
else
    echo "Service Account $BUILD_SA_EMAIL already exists."
fi

# 3. Grant IAM Roles to Cloud Build SA
echo "Granting roles to Cloud Build Service Account..."
# Allow deploying to Cloud Run
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$BUILD_SA_EMAIL" \
    --role="roles/run.admin"

# Allow impersonating other service accounts (needed for Cloud Run deploy)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$BUILD_SA_EMAIL" \
    --role="roles/iam.serviceAccountUser"

# Allow accessing Secret Manager (for build-time secrets and validation)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$BUILD_SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor"

# Allow viewing Secret metadata (needed for 'gcloud secrets describe' in deploy.sh)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$BUILD_SA_EMAIL" \
    --role="roles/secretmanager.viewer"

# Allow writing logs
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$BUILD_SA_EMAIL" \
    --role="roles/logging.logWriter"

# 4. Create Runtime Service Account (Recommended for Backend)
echo "Creating Backend Runtime Service Account..."
if ! gcloud iam service-accounts describe "$RUNTIME_SA_EMAIL" --project "$PROJECT_ID" > /dev/null 2>&1; then
    gcloud iam service-accounts create "$RUNTIME_SA_NAME" \
        --display-name="Backend Runtime Service Account" \
        --project "$PROJECT_ID"
else
    echo "Service Account $RUNTIME_SA_EMAIL already exists."
fi

# 5. Grant Runtime SA permissions (example: Secret Accessor)
# This allows the RUNNING Backend to access the secrets it needs.
echo "Granting Secret Accessor to Runtime SA..."
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:$RUNTIME_SA_EMAIL" \
    --role="roles/secretmanager.secretAccessor"

# 6. Instructions for Secrets
echo ""
echo "=========================================================="
echo "ACTION REQUIRED: Create Secrets"
echo "=========================================================="
echo "Run the following commands to create your secrets if they don't exist:"
echo ""
echo "  printf 'YOUR_EXPO_TOKEN' | gcloud secrets create EXPO_TOKEN --data-file=-"
echo "  # Add other secrets used in deploy.sh: SECRET_KEY, CLIENT_IDs, etc."
echo ""
echo "To use a keystore for Android (if not using EAS credentials):"
echo "  # Make sure your upload-keystore.jks is in the current directory or provide path"
echo "  base64 -i flutter/android/app/upload-keystore.jks | gcloud secrets create android-keystore --data-file=-"
echo ""

# 7. Instructions for Trigger
echo "=========================================================="
echo "ACTION REQUIRED: Create Cloud Build Trigger"
echo "=========================================================="
echo "1. Go to https://console.cloud.google.com/cloud-build/triggers"
echo "2. Click 'Create Trigger'"
echo "3. Name: 'deploy-on-main'"
echo "4. Event: 'Push to a branch'"
echo "5. Repository: Connect your GitHub repo '$GITHUB_REPO_OWNER/$GITHUB_REPO_NAME'"
echo "6. Branch: '^main$'"
echo "7. Configuration: 'Cloud Build configuration file (yaml/json)'"
echo "8. Location: 'cloudbuild.yaml'"
echo "9. Service Account: Select '$BUILD_SA_EMAIL'"
echo "10. Click 'Create'"
echo ""
echo "Done!"
