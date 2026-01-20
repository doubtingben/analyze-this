# Analyze This

## Description

Analyze This is a tool to review media shared through web or mobile interface through the "share this" feature. The tool will analyze the media looking for dates, locations, and principals.

In the default case, provided a date and time are provided, the tool will update the ical feed it serves with the new event. When information is missing, the tool will create a follow up for human media enrichment.

## Setup

### Mobile App

The mobile application is located in the `mobile/` directory and uses React Native (Expo).

1.  **Navigate to directory**: `cd mobile`
2.  **Install dependencies**: `npm install`
3.  **Run on iOS**: `npx expo run:ios` (Requires Xcode)
4.  **Run on Android**: `npx expo run:android` (Requires Android Studio)

**Important**: Testing the "Share" intent requires a Development Build (`npx expo run:ios/android`). It will not work in standard Expo Go.



### Running Analysis Tests

To run the analysis tests (located in `backend/tests/test_analysis.py`), execute the following command from the project root:

```bash
backend/.venv/bin/python backend/tests/test_analysis.py
```

## Local Development Environment

To run the project locally without modifying the production environment:

### Backend

1.  Navigate to `backend/`.
2.  Install dependencies: `pip install -r requirements.txt`.
3.  Run in development mode:
    ```bash
    APP_ENV=development uvicorn main:app --reload
    ```
    This will use a local SQLite database (`development.db`) instead of Firestore, and bypass Google Auth validation (accepting `dev-token`).

### Mobile App

1.  Run the app: `npx expo start`.
2.  In the Dashboard, tap the **Dev Login** button (visible only in dev builds). This authenticates you as a test user ("Developer") without needing Google Sign-In.

### Chrome Extension

1.  Ensure `extension/config.js` has `API_BASE_URL` set to `http://localhost:8000`.
2.  Load the extension unpacked in Chrome (Developer Mode).
