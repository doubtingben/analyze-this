# Analyze This

## Description

Analyze This is a tool to review media shared through web or mobile interface through the "share this" feature. The tool will analyze the media looking for dates, locations, and principals.

In the default case, provided a date and time are provided, the tool will update the ical feed it serves with the new event. When information is missing, the tool will create a follow up for human media enrichment.

## Setup

### Mobile App (Flutter)

The mobile application is located in the `flutter/` directory.

1.  **Navigate to directory**: `cd flutter`
2.  **Install dependencies**: `flutter pub get`
3.  **Run on iOS**: `flutter run -d ios` (Requires Xcode)
4.  **Run on Android**: `flutter run -d android` (Requires Android Studio)



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

### Mobile App (Flutter)

1.  Run the app: `flutter run`.
2.  In the Dashboard, tap the **Dev Login** button (visible only in dev builds). This authenticates you as a test user ("Developer") without needing Google Sign-In.

### Chrome Extension

1.  Ensure `extension/config.js` has `API_BASE_URL` set to `http://localhost:8000`.
2.  Load the extension unpacked in Chrome (Developer Mode).

## MCP Server for Application Monitoring

The project includes an MCP (Model Context Protocol) server that provides monitoring tools for AI agents and clients. The server allows querying user information, item processing status, worker queues, and error logs.

### Features

- **User Monitoring**: Get user statistics, item counts, and activity information
- **Worker Queue Status**: View current queue status, job types, and processing progress
- **Error Tracking**: Analyze failed jobs, group errors by type, and identify patterns
- **Item Status**: Filter and view items by processing status

### Quick Start

1. Install MCP dependency:
   ```bash
   cd backend
   pip install mcp
   ```

2. Run the MCP server:
   ```bash
   ./backend/run_mcp_server.sh
   ```

3. Configure your MCP client (e.g., Claude Desktop) to use the server. See `backend/MCP_SERVER.md` for detailed configuration instructions.

### Tools Available

- `get_users_info` - Summary of all users with item counts
- `get_user_details` - Detailed user information including tags and activity
- `get_worker_queue_status` - Current worker queue status and jobs
- `get_errors` - Error analysis from failed worker jobs
- `get_items_by_status` - Filter items by processing status

For complete documentation, see [backend/MCP_SERVER.md](backend/MCP_SERVER.md).
