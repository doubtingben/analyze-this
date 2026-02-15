#!/usr/bin/env bash
set -e

# Get the directory where the script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$BACKEND_DIR/.env"
PROJECT_ID="analyze-this-2026"

echo "Setting up secrets for project: $PROJECT_ID"

# 1. Enable Secret Manager API
echo "Enabling Secret Manager API (this may take a moment)..."
gcloud services enable secretmanager.googleapis.com --project "$PROJECT_ID"

# 2. Parse .env and create secrets
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at $ENV_FILE"
    exit 1
fi

echo "Reading secrets from $ENV_FILE..."

while IFS='=' read -r key value; do
    # Skip comments and empty lines
    if [[ $key =~ ^#.* ]] || [[ -z $key ]]; then
        continue
    fi

    echo "Processing $key..."

    # Check if secret exists
    if gcloud secrets describe "$key" --project "$PROJECT_ID" > /dev/null 2>&1; then
        echo "  Secret '$key' already exists. Updating version..."
        printf "%s" "$value" | gcloud secrets versions add "$key" --data-file=- --project "$PROJECT_ID"
    else
        echo "  Creating secret '$key'..."
        printf "%s" "$value" | gcloud secrets create "$key" --data-file=- --project "$PROJECT_ID"
    fi

done < "$ENV_FILE"

echo "Secret setup complete."
