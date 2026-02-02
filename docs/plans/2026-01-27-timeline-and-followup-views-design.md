# Timeline View & Follow-up Selector Design

## Overview

Add timeline view to Flutter app (matching web dashboard) and add follow-up selector to both web and Flutter UIs.

## Scope

| Platform | Current State | Changes |
|----------|--------------|---------|
| Web | Has "All \| Timeline" toggle | Add "Follow-up" as third option |
| Flutter | No filtering, flat list | Add "All \| Timeline \| Follow-up" toggles + type filter + timeline view |

Legacy mobile app is out of scope for this change.

## Data Filtering Logic

Same logic for both platforms:

- **All view**: All items, sorted by `created_at` descending (newest first)
- **Timeline view**: Items where `analysis.details.date_time` exists, sorted by event date ascending, with "Now" divider between past and future events
- **Follow-up view**: Items where `status === 'follow_up'`, sorted by `created_at` descending

**Type filter** (Flutter): Filters by item type (image, video, audio, file, screenshot, text, web_url). Applies on top of view filter.

No backend/API changes needed - all filtering is client-side using existing fields.

## Web Dashboard Changes

**Files:** `backend/static/index.html`, `backend/static/app.js`

### UI

```
[ All ] [ Timeline ] [ Follow-up ]    [Type Filter dropdown]
```

Third toggle button "Follow-up" added next to existing buttons, styled consistently.

### Code Changes

Add `follow_up` case to `getFilteredItems()`:

```javascript
if (currentView === 'follow_up') {
  items = items.filter(item => item.status === 'follow_up');
  items.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
}
```

## Flutter App Changes

**Files:** `flutter/lib/main.dart` (and potentially new widget files)

### UI Layout

```
+-------------------------------------+
|  Analyze This              refresh  |
+------------------------------------- +
|  [ All ] [ Timeline ] [ Follow-up ] |
|  [ All Types v ]                    |
+------------------------------------- +
|  +-----------------------------+    |
|  |  HistoryCard...             |    |
|  +-----------------------------+    |
```

### Components

1. **View Toggle**: `SegmentedButton` (Material 3) for All | Timeline | Follow-up
2. **Type Filter**: `DropdownMenu` (Material 3) with options: All Types, Image, Video, Audio, File, Screenshot, Text, Web URL
3. **Timeline "Now" Divider**: Horizontal line with centered "Now" label, matching web style

### State

Add to `_MyHomePageState`:

```dart
enum ViewMode { all, timeline, followUp }

ViewMode _currentView = ViewMode.all;
String? _currentTypeFilter; // null = all types
```

### Filtering

Create filtered items getter that:
1. Applies view filter (all/timeline/follow_up)
2. Applies type filter if set
3. Applies appropriate sorting

Timeline view inserts "Now" divider between past and future events based on `analysis.details.date_time`.

## Implementation Order

1. Web: Add follow-up toggle (small change)
2. Flutter: Add view mode state and segmented button
3. Flutter: Add type filter dropdown
4. Flutter: Implement filtering logic
5. Flutter: Add "Now" divider for timeline view
