# Firebase & Firestore Setup Guide

You are likely seeing an error because **Firestore requires a Composite Index** for queries that filter by one field (`user_email`) and sort by another (`created_at`).

## 1. Fixing the "Missing Index" Error
This is the most common issue. The backend tries to run this query:
```python
db.collection('shared_items').where('user_email', '==', user_email).order_by('created_at', DESCENDING)
```

### The Easy Fix (Recommended)
1.  Go to the **Google Cloud Console** > **Cloud Run**.
2.  Click on your service: `analyze-this-backend`.
3.  Go to the **Logs** tab.
4.  Trigger the error again (try to log in or load the dashboard).
5.  Look for a log entry marked with a **red error icon** (Error).
6.  Expand the error. You will see a message like:
    > "The query requires an index. You can create it here: https://console.firebase.google.com/v1/r/project/..."
7.  **Click that link**. It will take you directly to the Firebase Console with the correct index configuration pre-filled.
8.  Click **Create Index**. It may take 5-10 minutes to build.

### The Manual Fix
If you cannot find the link, you can create the index manually in the [Firebase Console](https://console.firebase.google.com/):
1.  Go to **Firestore Database** > **Indexes**.
2.  Click **Create Index**.
3.  **Collection ID**: `shared_items`
4.  **Fields Indexed**:
    *   `user_email` : **Ascending** (or Descending, equality doesn't matter much but usually Ascending)
    *   `created_at` : **Descending**
5.  **Query Scope**: Collection
6.  Click **Create**.

## 2. Other Requirements
If you haven't already:

### Enable Authentication
1.  Go to **Firebase Console** -> **Authentication**.
2.  Click **Get Started**.
3.  You don't necessarily need to enable any specific "Sign-in method" there if you are just using `firebase-admin` to manage the DB, but confirming the Auth service is "on" is good practice. *Note: Your app handles Auth via Google OAuth library, not Firebase Auth directly, so this is less critical unless we switch to Firebase Auth on the client.*

### Create the Database
(You mentioned you did this, but for reference):
1.  Go to **Firestore Database**.
2.  Click **Create Database**.
3.  Select **Production Mode**.
4.  Choose location `us-central1` (same as Cloud Run).

## 3. Verify OAuth
Ensure your **OAuth 2.0 Client ID** in GCP Console has the correct **Authorized redirect URIs**:
- `https://analyze-this-backend-106064975526.us-central1.run.app/auth`
- `https://interestedparticipant.org/auth` (if/when domain is mapped)
