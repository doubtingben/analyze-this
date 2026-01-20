# Dashboard Redesign

## Overview

Update the backend dashboard to match the mobile app's visual style, with type-specific rendering for different item types. Reorganize from embedded HTML to a static HTML + JavaScript architecture.

## Goals

- Match mobile app's visual style (color-coded type badges, card design)
- Show type-appropriate content (images as thumbnails, URLs with titles, etc.)
- Clean code separation (HTML, CSS, JS in separate files)
- No changes to existing mobile app API endpoints

## File Structure

```
backend/
├── static/
│   ├── index.html      # Dashboard markup
│   ├── styles.css      # All styling
│   └── app.js          # Fetch data, render items, handle actions
├── main.py             # Simplified - serves static files + API endpoints
```

## API Changes

### New Endpoints

- `GET /api/user` - Return current user info (email), or 401 if not authenticated
- `GET /api/items` - Return user's items as JSON array

### Modified Endpoints

- `GET /` - Serve `static/index.html` instead of server-rendered HTML

### Unchanged Endpoints

- `/login`, `/logout`, `/auth/callback` - OAuth flow
- `/share` (POST) - Mobile app item creation
- `/items/{item_id}` (DELETE) - Item deletion (ensure JSON response)

## Authentication Flow

1. Page loads `static/index.html`
2. JS calls `GET /api/user`
3. If 401 → redirect to `/login`
4. If authenticated → fetch items from `/api/items` and render

## Visual Design

### Color-Coded Type Badges

| Type    | Color   | Hex       |
|---------|---------|-----------|
| Media   | Green   | `#22c55e` |
| Web URL | Blue    | `#3b82f6` |
| File    | Orange  | `#f97316` |
| Text    | Grey    | `#6b7280` |

### Card Design

- White background with subtle border (`#e5e7eb`)
- 12px padding, 8px border radius
- Type badge as small colored pill in top-right
- Timestamp in grey below content
- Delete button (red, appears on hover)

### Type-Specific Rendering

**Media:**
- Show image thumbnail (max-height ~200px, object-fit: cover)
- Fallback icon if image fails to load

**Web URL:**
- Title as main text (from `item.title` or `item_metadata.title`)
- Favicon + domain in smaller grey text below
- Clickable link icon to open in new tab
- Falls back to raw URL if no title available

**Text:**
- Show content with 3-line truncation
- Expand on click to show full content

**File:**
- File icon + filename

### Layout

- Max-width 800px, centered
- Cards stacked vertically with 16px gap
- Header: "Analyze This" title + user email + logout link

## JavaScript Structure

```
init()              → Check auth, load items, set up event listeners
fetchUser()         → GET /api/user, handle 401 redirect
fetchItems()        → GET /api/items, return JSON array
renderItems(items)  → Clear container, call renderItem for each
renderItem(item)    → Switch on item.type, return appropriate HTML
deleteItem(id)      → DELETE /api/items/{id}, remove from DOM

// Type-specific renderers
renderMediaItem(item)   → Image thumbnail with fallback
renderWebUrlItem(item)  → Title + favicon + domain + link
renderTextItem(item)    → Truncated text, expand on click
renderFileItem(item)    → File icon + filename
```

### Error Handling

- Show friendly message if items fail to load
- Toast/alert on delete failure
- Graceful fallback if image fails to load

## HTML Structure

```html
<div class="container">
    <header>
        <h1>Analyze This</h1>
        <div class="user-info">
            <span id="user-email"></span>
            <a href="/logout">Logout</a>
        </div>
    </header>

    <main>
        <h2>Shared Items</h2>
        <div id="items-container"></div>
        <div id="empty-state" class="hidden">
            No items yet. Share something from the mobile app!
        </div>
        <div id="loading-state">Loading...</div>
    </main>
</div>
```

## Backend Changes Summary

### Remove from `main.py`

- Inline HTML template string (current lines 88-137)
- Server-side rendering logic in the `/` route

### Add to `main.py`

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Static file serving
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve dashboard
@app.get("/")
async def dashboard():
    return FileResponse("static/index.html")

# New API endpoints
@app.get("/api/user")
async def get_current_user(request: Request):
    # Return user info from session, or 401

@app.get("/api/items")
async def get_items(request: Request):
    # Same Firestore query, return JSON instead of HTML
```
