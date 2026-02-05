# Media View Implementation Plan

> **For Claude:** Use subagent-driven development to implement this plan task-by-task.

**Goal:** Add a "Media" view that shows items tagged with `to_read`, `to_listen`, or `to_watch`, grouped by tag and sorted by consumption time.

**Architecture:** Client-side filtering/grouping. Items appear in all matching tag groups. Sort by `consumption_time_minutes` (from AI analysis) ascending. Future-dated items get "Available [date]" indicator.

**Tech Stack:** Python/FastAPI (backend prompt only), Flutter/Dart (mobile), Vanilla JS (web)

---

## Task 1: Update analysis prompt to include consumption_time_minutes

**Files:**
- Modify: `backend/prompts/analysis.md`

**Changes:**

1. Add `consumption_time_minutes` to the JSON output schema description:
```
- consumption_time_minutes: Integer estimate of how long it takes to consume this content. For articles, estimate reading time (~200-250 words/minute). For videos/audio, use duration from metadata or estimate from description. For books, estimate total hours converted to minutes. Return null if not applicable (e.g., a calendar event, receipt, or non-consumable content).
```

2. Add guidance in the prompt body explaining when to include this field:
```
For media content (articles, videos, podcasts, books, etc.), estimate consumption_time_minutes. This helps users prioritize what to read/watch/listen to. For non-media items (events, receipts, tasks), set to null.
```

---

## Task 2: Flutter - Add Media view mode and state

**Files:**
- Modify: `flutter/lib/main.dart`

**Changes:**

1. Add `media` to the `ViewMode` enum:
```dart
enum ViewMode { all, timeline, followUp, media }
```

2. Define the media tags constant:
```dart
const Set<String> _mediaTags = {'to_read', 'to_listen', 'to_watch'};
```

3. Add helper method to get consumption time from an item:
```dart
int? _getConsumptionTime(HistoryItem item) {
  final analysis = item.analysis;
  if (analysis == null) return null;
  final time = analysis['consumption_time_minutes'];
  if (time is int) return time;
  if (time is num) return time.toInt();
  return null;
}
```

4. Add helper to check if item has future timeline date:
```dart
bool _isFutureAvailability(HistoryItem item) {
  final eventDate = _getEventDateTime(item);
  if (eventDate == null) return false;
  return eventDate.isAfter(DateTime.now());
}
```

5. Add helper to format availability date:
```dart
String _formatAvailabilityDate(DateTime date) {
  return DateFormat('MMM d').format(date);
}
```

---

## Task 3: Flutter - Update filtering logic for Media view

**Files:**
- Modify: `flutter/lib/main.dart`

**Changes:**

1. In `_getFilteredItems()`, add case for `ViewMode.media`:
```dart
case ViewMode.media:
  // Filter to items with any media tag
  items = items.where((item) {
    final tags = item.analysis?['tags'];
    if (tags is! List) return false;
    return tags.any((t) => _mediaTags.contains(t));
  }).toList();
  // Sort by consumption time (nulls last), then by timestamp
  items.sort((a, b) {
    final timeA = _getConsumptionTime(a);
    final timeB = _getConsumptionTime(b);
    if (timeA == null && timeB == null) return b.timestamp.compareTo(a.timestamp);
    if (timeA == null) return 1;
    if (timeB == null) return -1;
    return timeA.compareTo(timeB);
  });
  break;
```

2. Add method to group items by media tag for rendering:
```dart
Map<String, List<HistoryItem>> _groupItemsByMediaTag(List<HistoryItem> items) {
  final groups = <String, List<HistoryItem>>{
    'to_watch': [],
    'to_listen': [],
    'to_read': [],
  };

  for (final item in items) {
    final tags = item.analysis?['tags'];
    if (tags is! List) continue;
    for (final tag in _mediaTags) {
      if (tags.contains(tag)) {
        groups[tag]!.add(item);
      }
    }
  }

  // Sort each group by consumption time
  for (final group in groups.values) {
    group.sort((a, b) {
      final timeA = _getConsumptionTime(a);
      final timeB = _getConsumptionTime(b);
      if (timeA == null && timeB == null) return b.timestamp.compareTo(a.timestamp);
      if (timeA == null) return 1;
      if (timeB == null) return -1;
      return timeA.compareTo(timeB);
    });
  }

  return groups;
}
```

---

## Task 4: Flutter - Update UI for Media view

**Files:**
- Modify: `flutter/lib/main.dart`

**Changes:**

1. Add "Media" segment to the `SegmentedButton` in `_buildFilterControls()`:
```dart
ButtonSegment(
  value: ViewMode.media,
  label: const Text('Media'),
),
```

2. Update `_buildItemList()` to handle media view with grouped sections:
```dart
if (_currentView == ViewMode.media) {
  return _buildMediaList(filteredItems);
}
```

3. Add `_buildMediaList()` method:
```dart
Widget _buildMediaList(List<HistoryItem> items) {
  final groups = _groupItemsByMediaTag(items);
  final sections = <Widget>[];

  final groupLabels = {
    'to_watch': 'To Watch',
    'to_listen': 'To Listen',
    'to_read': 'To Read',
  };

  for (final tag in ['to_watch', 'to_listen', 'to_read']) {
    final groupItems = groups[tag]!;
    if (groupItems.isEmpty) continue;

    sections.add(
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
        child: Text(
          groupLabels[tag]!,
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );

    for (final item in groupItems) {
      sections.add(_buildItemCard(item, showConsumptionTime: true));
    }
  }

  if (sections.isEmpty) {
    return _buildEmptyState('No media items found');
  }

  return ListView(children: sections);
}
```

4. Update `_buildItemCard()` to accept optional `showConsumptionTime` parameter and display:
- Consumption time badge (e.g., "~15 min" or "~2 hr")
- "Available [date]" indicator for future-dated items

```dart
// Inside card, add consumption time if in media view
if (showConsumptionTime) {
  final time = _getConsumptionTime(item);
  if (time != null) {
    // Show "~X min" or "~X hr" badge
  }
  if (_isFutureAvailability(item)) {
    final date = _getEventDateTime(item)!;
    // Show "Available MMM d" badge
  }
}
```

5. Add helper to format consumption time:
```dart
String _formatConsumptionTime(int minutes) {
  if (minutes < 60) return '~$minutes min';
  final hours = minutes / 60;
  if (hours < 10) return '~${hours.toStringAsFixed(1)} hr';
  return '~${hours.round()} hr';
}
```

6. Update empty state message in `_buildEmptyState()` to handle media view case.

---

## Task 5: Web UI - Add Media view state and filtering

**Files:**
- Modify: `backend/static/app.js`

**Changes:**

1. Add media tags constant:
```javascript
const MEDIA_TAGS = new Set(['to_read', 'to_listen', 'to_watch']);
```

2. Add helper functions:
```javascript
function getConsumptionTime(item) {
  const time = item.analysis?.consumption_time_minutes;
  if (typeof time === 'number') return Math.round(time);
  return null;
}

function isFutureAvailability(item) {
  const eventDate = getEventDateTime(item);
  if (!eventDate) return false;
  return eventDate > new Date();
}

function formatConsumptionTime(minutes) {
  if (minutes < 60) return `~${minutes} min`;
  const hours = minutes / 60;
  if (hours < 10) return `~${hours.toFixed(1)} hr`;
  return `~${Math.round(hours)} hr`;
}

function formatAvailabilityDate(date) {
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
```

3. Add function to group items by media tag:
```javascript
function groupItemsByMediaTag(items) {
  const groups = {
    to_watch: [],
    to_listen: [],
    to_read: [],
  };

  for (const item of items) {
    const tags = item.analysis?.tags || [];
    for (const tag of MEDIA_TAGS) {
      if (tags.includes(tag)) {
        groups[tag].push(item);
      }
    }
  }

  // Sort each group by consumption time (nulls last)
  for (const group of Object.values(groups)) {
    group.sort((a, b) => {
      const timeA = getConsumptionTime(a);
      const timeB = getConsumptionTime(b);
      if (timeA === null && timeB === null) return (b.created_at || 0) - (a.created_at || 0);
      if (timeA === null) return 1;
      if (timeB === null) return -1;
      return timeA - timeB;
    });
  }

  return groups;
}
```

4. Update `getFilteredItems()` to handle `currentView === 'media'`:
```javascript
case 'media':
  items = items.filter(item => {
    const tags = item.analysis?.tags || [];
    return tags.some(t => MEDIA_TAGS.has(t));
  });
  // Sorting happens in groupItemsByMediaTag
  break;
```

---

## Task 6: Web UI - Add Media view HTML and rendering

**Files:**
- Modify: `backend/static/index.html`
- Modify: `backend/static/app.js`
- Modify: `backend/static/styles.css`

**HTML Changes (`index.html`):**

1. Add Media button to view toggle (after Follow-up button):
```html
<button class="view-toggle-btn" data-view="media">Media</button>
```

**JS Changes (`app.js`):**

1. Update `renderFilteredItems()` to handle media view:
```javascript
if (currentView === 'media') {
  renderMediaList(items);
  return;
}
```

2. Add `renderMediaList()` function:
```javascript
function renderMediaList(items) {
  const groups = groupItemsByMediaTag(items);
  const container = document.getElementById('items-container');
  container.innerHTML = '';

  const groupLabels = {
    to_watch: 'To Watch',
    to_listen: 'To Listen',
    to_read: 'To Read',
  };

  let hasAnyItems = false;

  for (const tag of ['to_watch', 'to_listen', 'to_read']) {
    const groupItems = groups[tag];
    if (groupItems.length === 0) continue;

    hasAnyItems = true;

    // Add section header
    const header = document.createElement('div');
    header.className = 'media-section-header';
    header.textContent = groupLabels[tag];
    container.appendChild(header);

    // Add items
    for (const item of groupItems) {
      const itemEl = createItemElement(item, { showConsumptionTime: true });
      container.appendChild(itemEl);
    }
  }

  if (!hasAnyItems) {
    container.innerHTML = '<div class="empty-state">No media items found</div>';
  }
}
```

3. Update `createItemElement()` to accept options and show:
- Consumption time badge
- "Available [date]" indicator for future items

**CSS Changes (`styles.css`):**

1. Add styles for media section header:
```css
.media-section-header {
  font-size: 1.1rem;
  font-weight: 600;
  padding: 16px 16px 8px;
  color: var(--text-primary);
  border-bottom: 1px solid var(--border-color);
  margin-bottom: 8px;
}
```

2. Add styles for consumption time badge:
```css
.consumption-time-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  color: #6b7280;
  background: #f3f4f6;
  padding: 2px 8px;
  border-radius: 12px;
}
```

3. Add styles for availability badge:
```css
.availability-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 0.75rem;
  color: #9333ea;
  background: #f3e8ff;
  padding: 2px 8px;
  border-radius: 12px;
}
```

---

## Verification

**Syntax check:**
```bash
cd backend && python3 -c "import ast; ast.parse(open('prompts/analysis.md').read()); print('OK')" || echo "Prompt is markdown, not Python - OK"
```

**Flutter analyze:**
```bash
cd flutter && flutter analyze
```

**Manual verification:**
- [ ] New item with article link gets `consumption_time_minutes` in analysis
- [ ] Media view shows in Flutter toolbar
- [ ] Media view shows in web toolbar
- [ ] Items with `to_watch` tag appear in "To Watch" section
- [ ] Items with `to_listen` tag appear in "To Listen" section
- [ ] Items with `to_read` tag appear in "To Read" section
- [ ] Item with multiple media tags appears in multiple sections
- [ ] Items sorted by consumption time (shortest first, nulls last)
- [ ] Consumption time badge shows on items (e.g., "~15 min")
- [ ] Future-dated items show "Available [date]" indicator
- [ ] Empty groups are hidden
- [ ] "No media items found" shows when no matching items
