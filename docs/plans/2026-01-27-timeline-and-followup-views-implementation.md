# Timeline View & Follow-up Selector Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add timeline view to Flutter app and follow-up selector to both web and Flutter UIs.

**Architecture:** Client-side filtering using existing `status` and `analysis.details.date_time` fields. No backend changes. Web gets one new view toggle; Flutter gets view toggles + type filter from scratch.

**Tech Stack:** Vanilla JS (web), Flutter/Dart with Material 3 (mobile)

---

## Task 1: Web - Add Follow-up View Toggle

**Files:**
- Modify: `backend/static/index.html:89-92`
- Modify: `backend/static/app.js:19,219-248`

**Step 1: Add Follow-up button to HTML**

In `backend/static/index.html`, add the third button after the Timeline button (line 91):

```html
<div class="view-toggle">
    <button class="view-btn active" data-view="all">All</button>
    <button class="view-btn" data-view="timeline">Timeline</button>
    <button class="view-btn" data-view="follow_up">Follow-up</button>
</div>
```

**Step 2: Update getFilteredItems() in app.js**

In `backend/static/app.js`, update the `getFilteredItems()` function to handle `follow_up` view. Replace lines 227-245 with:

```javascript
// Apply view-specific filtering and sorting
if (currentView === 'timeline') {
    // Filter to only items with derived date/time
    items = items.filter(item => getEventDateTime(item) !== null);

    // Sort by event date/time (ascending - oldest first)
    items.sort((a, b) => {
        const dateA = getEventDateTime(a);
        const dateB = getEventDateTime(b);
        return dateA - dateB;
    });
} else if (currentView === 'follow_up') {
    // Filter to only items with follow_up status
    items = items.filter(item => item.status === 'follow_up');

    // Sort by created_at descending (newest first)
    items.sort((a, b) => {
        const dateA = new Date(a.created_at || 0);
        const dateB = new Date(b.created_at || 0);
        return dateB - dateA;
    });
} else {
    // Default: sort by created_at descending (newest first)
    items.sort((a, b) => {
        const dateA = new Date(a.created_at || 0);
        const dateB = new Date(b.created_at || 0);
        return dateB - dateA;
    });
}
```

**Step 3: Update empty state message for follow_up view**

In `backend/static/app.js`, update the `renderItems()` function around line 295-301 to add follow_up case:

```javascript
if (currentView === 'timeline') {
    emptyStateEl.querySelector('p').textContent = 'No items with event dates found.';
} else if (currentView === 'follow_up') {
    emptyStateEl.querySelector('p').textContent = 'No items need follow-up.';
} else if (currentTypeFilter) {
    emptyStateEl.querySelector('p').textContent = `No ${formatType(currentTypeFilter)} items found.`;
} else {
    emptyStateEl.querySelector('p').textContent = 'No items yet. Share something from the mobile app or browser extension!';
}
```

**Step 4: Test manually**

1. Run backend: `cd backend && python -m uvicorn main:app --reload`
2. Open http://localhost:8000 in browser
3. Verify three view toggles appear: All | Timeline | Follow-up
4. Click each toggle and verify filtering works
5. Follow-up view should show only items with `status === 'follow_up'`

**Step 5: Commit**

```bash
git add backend/static/index.html backend/static/app.js
git commit -m "feat(web): add follow-up view toggle to dashboard"
```

---

## Task 2: Flutter - Add ViewMode Enum and State

**Files:**
- Modify: `flutter/lib/main.dart:41-50`

**Step 1: Add ViewMode enum and state variables**

After the imports (around line 14), add the enum:

```dart
enum ViewMode { all, timeline, followUp }
```

In `_MyHomePageState` class, add state variables after line 49 (`_authToken`):

```dart
ViewMode _currentView = ViewMode.all;
String? _currentTypeFilter;
```

**Step 2: Commit**

```bash
git add flutter/lib/main.dart
git commit -m "feat(flutter): add ViewMode enum and filter state"
```

---

## Task 3: Flutter - Add Filter Controls UI

**Files:**
- Modify: `flutter/lib/main.dart:286-334`

**Step 1: Create filter controls widget method**

Add this method to `_MyHomePageState` class (before `_buildEmptyState`):

```dart
Widget _buildFilterControls() {
  return Container(
    padding: const EdgeInsets.symmetric(
      horizontal: AppSpacing.lg,
      vertical: AppSpacing.md,
    ),
    decoration: BoxDecoration(
      color: AppColors.surface,
      border: Border(
        bottom: BorderSide(color: Colors.grey.shade200),
      ),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // View mode segmented button
        SegmentedButton<ViewMode>(
          segments: const [
            ButtonSegment(value: ViewMode.all, label: Text('All')),
            ButtonSegment(value: ViewMode.timeline, label: Text('Timeline')),
            ButtonSegment(value: ViewMode.followUp, label: Text('Follow-up')),
          ],
          selected: {_currentView},
          onSelectionChanged: (Set<ViewMode> selection) {
            setState(() {
              _currentView = selection.first;
            });
          },
        ),
        const SizedBox(height: AppSpacing.sm),
        // Type filter dropdown
        DropdownMenu<String?>(
          initialSelection: _currentTypeFilter,
          hintText: 'All Types',
          onSelected: (String? value) {
            setState(() {
              _currentTypeFilter = value;
            });
          },
          dropdownMenuEntries: const [
            DropdownMenuEntry(value: null, label: 'All Types'),
            DropdownMenuEntry(value: 'image', label: 'Image'),
            DropdownMenuEntry(value: 'video', label: 'Video'),
            DropdownMenuEntry(value: 'audio', label: 'Audio'),
            DropdownMenuEntry(value: 'file', label: 'File'),
            DropdownMenuEntry(value: 'screenshot', label: 'Screenshot'),
            DropdownMenuEntry(value: 'text', label: 'Text'),
            DropdownMenuEntry(value: 'web_url', label: 'Web URL'),
          ],
        ),
      ],
    ),
  );
}
```

**Step 2: Add filter controls to main view**

Update `_buildMainView()` to include filter controls. Replace the method with:

```dart
Widget _buildMainView() {
  return Column(
    children: [
      // User header
      Container(
        padding: const EdgeInsets.all(AppSpacing.lg),
        color: AppColors.surface,
        child: Row(
          children: [
            if (_currentUser!.photoUrl != null)
              CircleAvatar(
                radius: 20,
                backgroundImage: NetworkImage(_currentUser!.photoUrl!),
              ),
            const SizedBox(width: AppSpacing.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Welcome back,',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  Text(
                    _currentUser!.displayName ?? 'User',
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
      const Divider(height: 1),

      // Filter controls
      _buildFilterControls(),

      // Content
      Expanded(
        child: _isLoading
            ? Center(
                child: CircularProgressIndicator(
                  color: AppColors.primary,
                ),
              )
            : _getFilteredItems().isEmpty
                ? _buildEmptyState()
                : _buildHistoryList(),
      ),
    ],
  );
}
```

**Step 3: Commit**

```bash
git add flutter/lib/main.dart
git commit -m "feat(flutter): add view toggle and type filter UI"
```

---

## Task 4: Flutter - Implement Filtering Logic

**Files:**
- Modify: `flutter/lib/main.dart`

**Step 1: Add helper to get event datetime from item**

Add this method to `_MyHomePageState`:

```dart
DateTime? _getEventDateTime(HistoryItem item) {
  if (item.analysis == null) return null;
  final details = item.analysis!['details'] as Map<String, dynamic>?;
  if (details == null) return null;

  final dateTimeStr = details['date_time'] ??
                      details['dateTime'] ??
                      details['date'] ??
                      details['event_date'] ??
                      details['eventDate'] ??
                      details['start_date'];

  if (dateTimeStr == null) return null;

  try {
    return DateTime.parse(dateTimeStr.toString());
  } catch (e) {
    return null;
  }
}
```

**Step 2: Add filtering method**

Add this method to `_MyHomePageState`:

```dart
List<HistoryItem> _getFilteredItems() {
  List<HistoryItem> items = List.from(_history);

  // Apply type filter
  if (_currentTypeFilter != null) {
    items = items.where((item) => item.type == _currentTypeFilter).toList();
  }

  // Apply view-specific filtering and sorting
  switch (_currentView) {
    case ViewMode.timeline:
      items = items.where((item) => _getEventDateTime(item) != null).toList();
      items.sort((a, b) {
        final dateA = _getEventDateTime(a)!;
        final dateB = _getEventDateTime(b)!;
        return dateA.compareTo(dateB);
      });
      break;
    case ViewMode.followUp:
      items = items.where((item) => item.status == 'follow_up').toList();
      items.sort((a, b) => b.timestamp.compareTo(a.timestamp));
      break;
    case ViewMode.all:
    default:
      items.sort((a, b) => b.timestamp.compareTo(a.timestamp));
      break;
  }

  return items;
}
```

**Step 3: Update _buildHistoryList to use filtered items**

Replace `_buildHistoryList()` method:

```dart
Widget _buildHistoryList() {
  final items = _getFilteredItems();

  if (_currentView == ViewMode.timeline) {
    return _buildTimelineList(items);
  }

  return ListView.builder(
    padding: const EdgeInsets.all(AppSpacing.lg),
    itemCount: items.length,
    itemBuilder: (context, index) {
      final item = items[index];
      return Padding(
        padding: EdgeInsets.only(
          bottom: index < items.length - 1 ? AppSpacing.md : 0,
        ),
        child: HistoryCard(
          item: item,
          authToken: _authToken,
          onTap: () => _openDetailFiltered(items, index),
          onDelete: () => _deleteItem(item),
        ),
      );
    },
  );
}
```

**Step 4: Update _openDetail to work with filtered list**

Add new method and keep old one for compatibility:

```dart
void _openDetailFiltered(List<HistoryItem> items, int index) {
  Navigator.of(context).push(
    MaterialPageRoute(
      builder: (context) => ItemDetailScreen(
        items: items,
        initialIndex: index,
        authToken: _authToken,
      ),
    ),
  );
}
```

**Step 5: Commit**

```bash
git add flutter/lib/main.dart
git commit -m "feat(flutter): implement view filtering logic"
```

---

## Task 5: Flutter - Add Timeline View with Now Divider

**Files:**
- Modify: `flutter/lib/main.dart`

**Step 1: Add Now divider widget method**

Add this method to `_MyHomePageState`:

```dart
Widget _buildNowDivider() {
  return Padding(
    padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
    child: Row(
      children: [
        Expanded(
          child: Container(
            height: 2,
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF3b82f6), Color(0xFF8b5cf6)],
              ),
            ),
          ),
        ),
        Container(
          margin: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.lg,
            vertical: AppSpacing.xs,
          ),
          decoration: BoxDecoration(
            gradient: const LinearGradient(
              colors: [Color(0xFF3b82f6), Color(0xFF8b5cf6)],
            ),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Text(
            'NOW',
            style: TextStyle(
              color: Colors.white,
              fontSize: 12,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.5,
            ),
          ),
        ),
        Expanded(
          child: Container(
            height: 2,
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                colors: [Color(0xFF8b5cf6), Color(0xFF3b82f6)],
              ),
            ),
          ),
        ),
      ],
    ),
  );
}
```

**Step 2: Add event date badge widget method**

Add this method to `_MyHomePageState`:

```dart
Widget _buildEventDateBadge(DateTime eventDate) {
  final dateStr = DateFormat('E, MMM d, h:mm a').format(eventDate);
  return Container(
    width: double.infinity,
    padding: const EdgeInsets.symmetric(
      horizontal: AppSpacing.md,
      vertical: AppSpacing.sm,
    ),
    decoration: BoxDecoration(
      gradient: LinearGradient(
        colors: [Colors.blue.shade50, Colors.purple.shade50],
      ),
      borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
    ),
    child: Text(
      dateStr,
      style: TextStyle(
        color: Colors.indigo.shade600,
        fontSize: 12,
        fontWeight: FontWeight.w500,
      ),
    ),
  );
}
```

**Step 3: Add timeline list builder method**

Add this method to `_MyHomePageState`:

```dart
Widget _buildTimelineList(List<HistoryItem> items) {
  final now = DateTime.now();
  int nowIndex = items.length; // Default: Now at end

  // Find where to insert Now divider
  for (int i = 0; i < items.length; i++) {
    final eventDate = _getEventDateTime(items[i]);
    if (eventDate != null && eventDate.isAfter(now)) {
      nowIndex = i;
      break;
    }
  }

  // Total items = items + 1 for Now divider
  final totalCount = items.length + 1;

  return ListView.builder(
    padding: const EdgeInsets.all(AppSpacing.lg),
    itemCount: totalCount,
    itemBuilder: (context, index) {
      // Insert Now divider at the right position
      if (index == nowIndex) {
        return _buildNowDivider();
      }

      // Adjust item index based on Now divider position
      final itemIndex = index > nowIndex ? index - 1 : index;
      final item = items[itemIndex];
      final eventDate = _getEventDateTime(item);

      return Padding(
        padding: EdgeInsets.only(
          bottom: index < totalCount - 1 ? AppSpacing.md : 0,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (eventDate != null) _buildEventDateBadge(eventDate),
            HistoryCard(
              item: item,
              authToken: _authToken,
              onTap: () => _openDetailFiltered(items, itemIndex),
              onDelete: () => _deleteItem(item),
            ),
          ],
        ),
      );
    },
  );
}
```

**Step 4: Add intl import for DateFormat**

At the top of the file, ensure this import exists:

```dart
import 'package:intl/intl.dart';
```

**Step 5: Commit**

```bash
git add flutter/lib/main.dart
git commit -m "feat(flutter): add timeline view with Now divider"
```

---

## Task 6: Flutter - Update Empty State Messages

**Files:**
- Modify: `flutter/lib/main.dart`

**Step 1: Update _buildEmptyState to be view-aware**

Replace `_buildEmptyState()` method:

```dart
Widget _buildEmptyState() {
  String message;
  IconData icon;

  switch (_currentView) {
    case ViewMode.timeline:
      message = 'No items with event dates found';
      icon = Icons.event_outlined;
      break;
    case ViewMode.followUp:
      message = 'No items need follow-up';
      icon = Icons.check_circle_outline;
      break;
    case ViewMode.all:
    default:
      if (_currentTypeFilter != null) {
        message = 'No ${_currentTypeFilter} items found';
        icon = Icons.filter_list_off;
      } else {
        message = 'No items yet';
        icon = Icons.inbox_outlined;
      }
      break;
  }

  return Center(
    child: Padding(
      padding: const EdgeInsets.all(AppSpacing.xl),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            icon,
            size: 48,
            color: AppColors.textSecondary,
          ),
          const SizedBox(height: AppSpacing.lg),
          Text(
            message,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            _currentView == ViewMode.all && _currentTypeFilter == null
                ? 'Share content from other apps to see it here'
                : 'Try changing your filters',
            style: Theme.of(context).textTheme.bodySmall,
            textAlign: TextAlign.center,
          ),
        ],
      ),
    ),
  );
}
```

**Step 2: Commit**

```bash
git add flutter/lib/main.dart
git commit -m "feat(flutter): update empty state for different views"
```

---

## Task 7: Test End-to-End

**Step 1: Test web dashboard**

1. Run backend: `cd backend && python -m uvicorn main:app --reload`
2. Open http://localhost:8000
3. Test All | Timeline | Follow-up toggles
4. Test type filter dropdown
5. Verify combination of view + type filter works

**Step 2: Test Flutter app**

1. Run Flutter app: `cd flutter && flutter run`
2. Sign in with Google
3. Test All | Timeline | Follow-up segmented button
4. Test type filter dropdown
5. Verify timeline view shows Now divider in correct position
6. Verify event date badges appear on timeline items
7. Test empty states for each view mode

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: add timeline view and follow-up selector to web and Flutter

- Web: Add Follow-up as third view toggle
- Flutter: Add view mode segmented button (All/Timeline/Follow-up)
- Flutter: Add type filter dropdown
- Flutter: Timeline view with Now divider and event date badges
- Flutter: Context-aware empty states"
```
