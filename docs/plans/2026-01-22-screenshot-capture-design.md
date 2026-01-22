# Full-Page Screenshot Capture for Chrome Extension

## Overview

Replace the "Analyze this page" context menu behavior to capture a full-page screenshot using scroll-and-stitch instead of sending the page URL. This provides richer context for analysis when web pages don't render well from URLs alone.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Which pages | All "Analyze this page" clicks | Simpler UX, consistent behavior |
| Long page handling | Cap at ~15,000px height | Prevents runaway captures on infinite scroll |
| Image transfer | Multipart upload | Cleaner than base64, reuses existing upload infrastructure |
| User feedback | Overlay blocking interaction | Prevents scroll disruption during capture |

## Architecture

### Extension Changes

**Files affected:**
- `extension/background.js` - Modified context menu handler
- `extension/capture.js` - New content script for scroll-and-stitch
- `extension/manifest.json` - Verify permissions

### Capture Flow

```
User clicks "Analyze this page"
        │
        ▼
background.js injects capture.js into tab
        │
        ▼
capture.js shows blocking overlay
        │
        ▼
Loop: scroll → message background → captureVisibleTab() → return chunk
        │
        ▼
Stitch chunks on offscreen canvas
        │
        ▼
Export as JPEG blob (85% quality)
        │
        ▼
Remove overlay, restore scroll position
        │
        ▼
background.js uploads blob via multipart POST
        │
        ▼
Show success/failure notification
```

### Content Script: capture.js

Responsibilities:
1. Show/hide capture overlay with "Capturing page..." message
2. Calculate page dimensions, cap height at 15,000px
3. Coordinate scroll positions for capture
4. Message background script for each `captureVisibleTab()` call
5. Stitch captured chunks on canvas
6. Export final image as blob
7. Restore original scroll position (always, even on error)

### Background Script Changes

The `analyze-this-page` handler will:
1. Inject `capture.js` into the active tab
2. Listen for capture chunk requests, call `chrome.tabs.captureVisibleTab()`
3. Receive final blob from content script
4. Upload via multipart form to `/api/share`
5. Show notification on completion

### Backend Changes

**Endpoint:** `POST /api/share`

Modify to accept multipart form data:
- Detect `Content-Type: multipart/form-data`
- Extract `screenshot` file field
- Extract `title` and `type` form fields
- Save image using existing `save_media_file()` infrastructure
- Store resulting URL/path in `content` field

**New type value:** `"screenshot"` to distinguish from URL-based shares

## Error Handling

| Scenario | Handling |
|----------|----------|
| Restricted page (chrome://, extension pages) | Detect upfront, show "Cannot capture this page" |
| captureVisibleTab() fails | Abort with error notification |
| Stitching fails (memory) | Fall back to single viewport capture |
| Upload fails | Show error notification |
| Any error during capture | Restore scroll position, remove overlay |

## Performance Considerations

- 100ms delay between captures for page rendering
- 15,000px height cap prevents memory exhaustion
- JPEG at 85% quality balances size (~1-3MB) and clarity
- Offscreen canvas for stitching avoids DOM manipulation

## Testing Considerations

- Test on short pages (single viewport)
- Test on long pages (multiple viewports)
- Test on pages near/exceeding 15,000px cap
- Test on restricted pages (chrome://, PDF viewer)
- Test upload success/failure paths
- Test scroll restoration on error
