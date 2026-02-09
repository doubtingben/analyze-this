# Timeline Feature

## Overview
The Timeline is a **filtered view** of items that have derived date/time data from analysis. Instead of a complex calendar UI, it's a simple list with a "Now" divider that anchors you to the present moment.

## Views

### Default View (Chronological)
- All items sorted by `created_at` (when shared)
- Most recent first
- This is the existing behavior

### Type Filter
- Filter items by type: screenshot, image, web_url, text, video, audio, file
- Can be combined with other views
- Useful for finding specific content types

### Timeline View
- **Filters to**: Items with `analysis.details.date_time` (derived event time)
- **Sorted by**: The derived `date_time`, ascending (oldest to newest)
- **"Now" divider**: Visual separator between past and future items
- **Auto-scroll**: Opens with view centered on "Now"

```
┌─────────────────────────────┐
│ Jan 20 - Meeting notes      │  ↑ Past events
│ Jan 24 - Dinner reservation │
├────────── Now ──────────────┤  ← Initial scroll position
│ Jan 29 - Flor Fina Dinner   │  ↓ Future events
│ Feb 3 - Tech Conference     │
│ Feb 14 - Valentine's dinner │
└─────────────────────────────┘
```

## Data Requirements

For an item to appear in Timeline view, analysis must extract:

| Field | Location | Description |
|-------|----------|-------------|
| `date_time` | `analysis.details.date_time` | When the event occurs (ISO 8601) |
| `overview` | `analysis.overview` | Display text |

Optional fields that enhance display:
- `analysis.details.end_time` - Event end time
- `analysis.details.location` - Where (physical/virtual)
- `analysis.details.title` - Event title

## Implementation

### Web UI (backend/static/app.js)
- Add view toggle buttons: "All" | "Timeline"
- Add type filter dropdown
- Implement "Now" divider rendering
- Auto-scroll to "Now" on timeline view activation

### Mobile (Flutter)
- Similar controls in the history tab
- FlatList with section headers for "Past" / "Now" / "Upcoming"

## Why This Approach?

The original design called for a zoomable calendar with day/week/month/year views. This simpler approach:

1. **Reuses existing components** - It's still a list, just filtered and sorted differently
2. **Ships faster** - No complex calendar grid or time positioning logic
3. **Works on all screen sizes** - List UI is inherently responsive
4. **Preserves "nowness"** - The Now divider gives temporal context without calendar complexity
5. **Type filter is independently useful** - Even without timeline, filtering by type helps users find content
