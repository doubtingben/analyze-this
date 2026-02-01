# Context
You are a helpful assistant that builds a local development environment for a project.

If you run into any trouble while executing these instructions, please stop and ask for help. Do not try to fix the issue yourself, gather as much information as possible and ask for help. A meta goal of this process is to ensure the assumptions are correct and the environment is valid.

Before starting, make sure you have access to the following secrets:
- GITHUB_TOKEN
- PLAYSTORE_APP_SIGNING_KEY_PATH
- PLAYSTORE_UPLOAD_KEYSTORE_KEY_PROPERTIES_PATH
- GOOGLE_SERVICE_ACCOUNT_KEY_PATH

Test the secrets allow the following:
## GITHUB_TOKEN
- Test the token by cloning the repository
## PLAYSTORE_APP_SIGNING_KEY_PATH
- Verify the file exists and is readable
## PLAYSTORE_UPLOAD_KEYSTORE_KEY_PROPERTIES_PATH
- Verify the file exists and is readable
## GOOGLE_SERVICE_ACCOUNT_KEY_PATH
- Verify GCP project CloudRun Service access and Artifact Registry access

# Instructions
The first step is required before any other step.
The remaining steps can be run in parallel.
## Clone the repository
- Clone the REPO_URL using the GITHUB_TOKEN to a temporary directory
## Bump the version
- Update analyze_this_flutter/pubspec.yaml to increment the build number by 1
## Deploy the backend
- Generate a view of the existing Google Cloud Run service before we modify it and save it for later comparison
- Use the Makefile to deploy the backend, `make backend-deploy`
- Generate a view of the new Google Cloud Run service after deployment and compare the two views to ensure the service was modified as expected.
## Deploy the workers
- Use the ./backend/scripts/deploy-worker.sh script to deploy the analysis worker, `./backend/scripts/deploy-worker.sh analysis`
- Use the ./backend/scripts/deploy-worker.sh script to deploy the normalize worker, `./backend/scripts/deploy-worker.sh normalize`

## Build the Android Flutter mobile app
- Use the Makefile to Build Android App Bundle (Release)
## Build the iOS Flutter mobile app
- Use the Makefile to Build iOS app .ipa (Release, requires signing)

# Report
Provide a simple report with the success or failure of each step.
The report should just include the deployment branch and time of deployment.
The report should contain paths to the mobile app builds.

