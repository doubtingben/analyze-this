# Export Data Test Data Guide

This document describes the minimal dataset needed to validate the export feature end-to-end.

## Goal
Validate that export produces a ZIP containing:
- `items.json` with **all items**, including hidden/archived items
- `export_manifest.json` with a file list and metadata
- Binary files under `files/` for any items with stored content

## Required Items
Create at least the following items for a single user email (e.g. `dev@example.com`):

1) **Text item** (no file)
- `type`: `text`
- `content`: Any short string
- `title`: Optional
- `hidden`: `false`

2) **File item** (stored file)
- `type`: `file` (or `image`, `video`, `audio`, `screenshot`)
- `content`: `uploads/<user_email>/<filename>`
- `title`: Optional
- `hidden`: `true` (to ensure hidden items export)
- File must exist at:
  - Development: `backend/static/uploads/<user_email>/<filename>`
  - Production: Cloud Storage at the same path

## Optional Items (Nice to Have)
- Item with `analysis` populated (overview/timeline/tags) to ensure analysis data exports
- Item with `item_metadata` (file size, dimensions, duration)

## Expected Export Structure
The ZIP should contain:
- `items.json`: list of items with original fields + `export_file` for file-backed items
- `export_manifest.json`: metadata and `files` list with `export_path`
- `files/<item_id>_<basename>`: binary file content for each file-backed item

## Example Item JSON (for reference)
```json
{
  "id": "uuid",
  "user_email": "dev@example.com",
  "type": "file",
  "content": "uploads/dev@example.com/export-test.txt",
  "title": "Export File",
  "hidden": true,
  "analysis": {
    "overview": "Test Overview",
    "timeline": {"date": "2024-01-01"},
    "tags": ["tag1"]
  },
  "item_metadata": {"fileSize": 1234}
}
```
