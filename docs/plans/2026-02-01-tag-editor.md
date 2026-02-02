# Tag Editor Implementation Plan

> **For Claude:** Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add a Tag Editor screen accessible from the user dropdown menu that displays all tags with item counts, supports search/sort, and allows tag deletion.

**Architecture:** Client-side aggregation of tags from items. Flutter uses a dedicated screen (following MetricsScreen pattern), Web uses a modal (following existing modal patterns). Both compute tag statistics from loaded items and call existing PATCH endpoint to remove tags from items.

**Tech Stack:** Flutter/Dart (mobile), Vanilla JS + HTML/CSS (web)

---

## Task 1: Flutter - Create Tag Editor Screen

**Files:**
- Create: `flutter/lib/screens/tag_editor_screen.dart`

**Implementation:**

Create a StatefulWidget that displays all tags with their usage counts:

```dart
import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/history_item.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';

enum TagSortMode { name, newest, count }

class TagEditorScreen extends StatefulWidget {
  final String authToken;
  final List<HistoryItem> items;

  const TagEditorScreen({
    super.key,
    required this.authToken,
    required this.items,
  });

  @override
  State<TagEditorScreen> createState() => _TagEditorScreenState();
}

class _TagEditorScreenState extends State<TagEditorScreen> {
  final ApiService _apiService = ApiService();
  final TextEditingController _searchController = TextEditingController();

  String _searchQuery = '';
  TagSortMode _sortMode = TagSortMode.name;
  bool _isDeleting = false;

  /// Compute tag statistics from items
  List<TagInfo> _getTagStats() {
    final tagMap = <String, TagInfo>{};

    for (final item in widget.items) {
      final tags = item.analysis?['tags'];
      if (tags is List) {
        for (final tag in tags) {
          if (tag is String) {
            if (tagMap.containsKey(tag)) {
              tagMap[tag]!.count++;
              // Track newest item date for this tag
              if (item.createdAt.isAfter(tagMap[tag]!.newestDate)) {
                tagMap[tag]!.newestDate = item.createdAt;
              }
            } else {
              tagMap[tag] = TagInfo(
                name: tag,
                count: 1,
                newestDate: item.createdAt,
              );
            }
          }
        }
      }
    }

    var tags = tagMap.values.toList();

    // Filter by search
    if (_searchQuery.isNotEmpty) {
      final query = _searchQuery.toLowerCase();
      tags = tags.where((t) => t.name.toLowerCase().contains(query)).toList();
    }

    // Sort
    switch (_sortMode) {
      case TagSortMode.name:
        tags.sort((a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
      case TagSortMode.newest:
        tags.sort((a, b) => b.newestDate.compareTo(a.newestDate));
      case TagSortMode.count:
        tags.sort((a, b) => b.count.compareTo(a.count));
    }

    return tags;
  }

  Future<void> _deleteTag(String tagName) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Tag'),
        content: Text('Remove "$tagName" from all items? This cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirm != true) return;

    setState(() => _isDeleting = true);

    try {
      // Find all items with this tag and remove it
      final itemsWithTag = widget.items.where((item) {
        final tags = item.analysis?['tags'];
        return tags is List && tags.contains(tagName);
      }).toList();

      for (final item in itemsWithTag) {
        final currentTags = List<String>.from(item.analysis?['tags'] ?? []);
        currentTags.remove(tagName);
        await _apiService.updateItem(widget.authToken, item.id, tags: currentTags);

        // Update local item state
        if (item.analysis != null) {
          item.analysis!['tags'] = currentTags;
        }
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Removed "$tagName" from ${itemsWithTag.length} items')),
        );
        setState(() {}); // Refresh the list
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete tag: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isDeleting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final tags = _getTagStats();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Tag Editor'),
        actions: [
          PopupMenuButton<TagSortMode>(
            icon: const Icon(Icons.sort),
            tooltip: 'Sort by',
            onSelected: (mode) => setState(() => _sortMode = mode),
            itemBuilder: (context) => [
              PopupMenuItem(
                value: TagSortMode.name,
                child: Row(
                  children: [
                    if (_sortMode == TagSortMode.name)
                      const Icon(Icons.check, size: 18)
                    else
                      const SizedBox(width: 18),
                    const SizedBox(width: 8),
                    const Text('Name'),
                  ],
                ),
              ),
              PopupMenuItem(
                value: TagSortMode.newest,
                child: Row(
                  children: [
                    if (_sortMode == TagSortMode.newest)
                      const Icon(Icons.check, size: 18)
                    else
                      const SizedBox(width: 18),
                    const SizedBox(width: 8),
                    const Text('Newest'),
                  ],
                ),
              ),
              PopupMenuItem(
                value: TagSortMode.count,
                child: Row(
                  children: [
                    if (_sortMode == TagSortMode.count)
                      const Icon(Icons.check, size: 18)
                    else
                      const SizedBox(width: 18),
                    const SizedBox(width: 8),
                    const Text('Most Used'),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          // Search bar
          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: TextField(
              controller: _searchController,
              decoration: InputDecoration(
                hintText: 'Search tags...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchController.clear();
                          setState(() => _searchQuery = '');
                        },
                      )
                    : null,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              onChanged: (value) => setState(() => _searchQuery = value),
            ),
          ),

          // Tag count
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            child: Row(
              children: [
                Text(
                  '${tags.length} tag${tags.length == 1 ? '' : 's'}',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: AppSpacing.sm),

          // Tag list
          Expanded(
            child: _isDeleting
                ? const Center(child: CircularProgressIndicator())
                : tags.isEmpty
                    ? Center(
                        child: Text(
                          _searchQuery.isNotEmpty
                              ? 'No tags match "$_searchQuery"'
                              : 'No tags yet',
                          style: TextStyle(color: AppColors.textSecondary),
                        ),
                      )
                    : ListView.builder(
                        itemCount: tags.length,
                        itemBuilder: (context, index) {
                          final tag = tags[index];
                          return ListTile(
                            leading: CircleAvatar(
                              backgroundColor: AppColors.primary.withOpacity(0.1),
                              child: Icon(
                                Icons.label_outline,
                                color: AppColors.primary,
                              ),
                            ),
                            title: Text(tag.name),
                            subtitle: Text(
                              '${tag.count} item${tag.count == 1 ? '' : 's'}',
                            ),
                            trailing: IconButton(
                              icon: const Icon(Icons.delete_outline),
                              color: Colors.red.shade400,
                              onPressed: () => _deleteTag(tag.name),
                              tooltip: 'Delete tag',
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }
}

/// Tag information with statistics
class TagInfo {
  final String name;
  int count;
  DateTime newestDate;

  TagInfo({
    required this.name,
    required this.count,
    required this.newestDate,
  });
}
```

---

## Task 2: Flutter - Add Tag Editor to User Menu

**Files:**
- Modify: `flutter/lib/main.dart`

**Changes:**

1. Add import for the new screen at top of file:
```dart
import 'screens/tag_editor_screen.dart';
```

2. Add method to open tag editor (after `_openMetrics` method around line 432):
```dart
void _openTagEditor() {
  Navigator.pop(context); // Close the menu
  Navigator.push(
    context,
    MaterialPageRoute(
      builder: (context) => TagEditorScreen(
        authToken: _authToken!,
        items: _history,
      ),
    ),
  ).then((_) {
    // Refresh history when returning (tags may have been deleted)
    _loadHistory();
  });
}
```

3. Add Tag Editor menu item in `_showUserMenu()` after the Metrics ListTile:
```dart
ListTile(
  contentPadding: EdgeInsets.zero,
  leading: const Icon(Icons.label_outline),
  title: const Text('Tag Editor'),
  onTap: _openTagEditor,
),
```

---

## Task 3: Web - Add Tag Editor Modal HTML/CSS

**Files:**
- Modify: `backend/static/index.html`
- Modify: `backend/static/styles.css`

**HTML Changes:**

Add tag editor button to user menu (after metrics-btn):
```html
<button class="user-menu-item" id="tag-editor-btn">Tag Editor</button>
```

Add tag editor modal (after metrics-modal):
```html
<div id="tag-editor-modal" class="modal" style="display: none;">
    <div class="modal-backdrop" id="tag-editor-modal-backdrop"></div>
    <div class="modal-content modal-large">
        <div class="modal-header">
            <h2>Tag Editor</h2>
            <button class="modal-close" id="tag-editor-modal-close">&times;</button>
        </div>
        <div class="tag-editor-controls">
            <input type="text" id="tag-search-input" class="tag-search-input" placeholder="Search tags...">
            <select id="tag-sort-select" class="tag-sort-select">
                <option value="name">Sort by Name</option>
                <option value="newest">Sort by Newest</option>
                <option value="count">Sort by Most Used</option>
            </select>
        </div>
        <div class="tag-editor-count" id="tag-editor-count"></div>
        <div class="tag-editor-list" id="tag-editor-list"></div>
    </div>
</div>
```

**CSS Changes:**

Add styles for tag editor:
```css
/* Tag Editor Modal */
.tag-editor-controls {
    display: flex;
    gap: 12px;
    padding: 16px;
    border-bottom: 1px solid #e0e0e0;
}

.tag-search-input {
    flex: 1;
    padding: 8px 12px;
    border: 1px solid #ccc;
    border-radius: 6px;
    font-size: 14px;
}

.tag-search-input:focus {
    outline: none;
    border-color: #4285f4;
}

.tag-sort-select {
    padding: 8px 12px;
    border: 1px solid #ccc;
    border-radius: 6px;
    font-size: 14px;
    background: white;
    cursor: pointer;
}

.tag-editor-count {
    padding: 8px 16px;
    font-size: 12px;
    color: #666;
}

.tag-editor-list {
    max-height: 400px;
    overflow-y: auto;
}

.tag-editor-item {
    display: flex;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid #f0f0f0;
}

.tag-editor-item:hover {
    background: #f9f9f9;
}

.tag-editor-icon {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    background: #e8f0fe;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: 12px;
    color: #4285f4;
}

.tag-editor-info {
    flex: 1;
}

.tag-editor-name {
    font-weight: 500;
    margin-bottom: 2px;
}

.tag-editor-count-label {
    font-size: 12px;
    color: #666;
}

.tag-editor-delete {
    background: none;
    border: none;
    color: #d93025;
    cursor: pointer;
    padding: 8px;
    border-radius: 4px;
    opacity: 0.7;
}

.tag-editor-delete:hover {
    background: #fce8e6;
    opacity: 1;
}

.tag-editor-empty {
    padding: 40px;
    text-align: center;
    color: #666;
}
```

---

## Task 4: Web - Wire Up Tag Editor JavaScript

**Files:**
- Modify: `backend/static/app.js`

**Changes:**

1. Add DOM element references (near other modal refs around line 20):
```javascript
const tagEditorBtn = document.getElementById('tag-editor-btn');
const tagEditorModal = document.getElementById('tag-editor-modal');
const tagEditorModalBackdrop = document.getElementById('tag-editor-modal-backdrop');
const tagEditorModalClose = document.getElementById('tag-editor-modal-close');
const tagSearchInput = document.getElementById('tag-search-input');
const tagSortSelect = document.getElementById('tag-sort-select');
const tagEditorCount = document.getElementById('tag-editor-count');
const tagEditorList = document.getElementById('tag-editor-list');
```

2. Add tag editor state and functions (after setupUserMenu function):
```javascript
// Tag Editor State
let tagSearchQuery = '';
let tagSortMode = 'name';

function setupTagEditor() {
    if (tagEditorBtn) {
        tagEditorBtn.addEventListener('click', () => {
            closeUserMenu();
            openTagEditorModal();
        });
    }

    if (tagEditorModalClose) {
        tagEditorModalClose.addEventListener('click', closeTagEditorModal);
    }

    if (tagEditorModalBackdrop) {
        tagEditorModalBackdrop.addEventListener('click', closeTagEditorModal);
    }

    if (tagSearchInput) {
        tagSearchInput.addEventListener('input', (e) => {
            tagSearchQuery = e.target.value;
            renderTagEditorList();
        });
    }

    if (tagSortSelect) {
        tagSortSelect.addEventListener('change', (e) => {
            tagSortMode = e.target.value;
            renderTagEditorList();
        });
    }
}

function openTagEditorModal() {
    tagSearchQuery = '';
    tagSearchInput.value = '';
    tagSortMode = 'name';
    tagSortSelect.value = 'name';
    renderTagEditorList();
    tagEditorModal.style.display = 'flex';
}

function closeTagEditorModal() {
    tagEditorModal.style.display = 'none';
}

function getTagStats() {
    const tagMap = {};

    allItems.forEach(item => {
        const tags = item.analysis?.tags || [];
        tags.forEach(tag => {
            if (!tagMap[tag]) {
                tagMap[tag] = {
                    name: tag,
                    count: 0,
                    newestDate: new Date(0)
                };
            }
            tagMap[tag].count++;
            const itemDate = new Date(item.created_at);
            if (itemDate > tagMap[tag].newestDate) {
                tagMap[tag].newestDate = itemDate;
            }
        });
    });

    let tags = Object.values(tagMap);

    // Filter by search
    if (tagSearchQuery) {
        const query = tagSearchQuery.toLowerCase();
        tags = tags.filter(t => t.name.toLowerCase().includes(query));
    }

    // Sort
    switch (tagSortMode) {
        case 'name':
            tags.sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
            break;
        case 'newest':
            tags.sort((a, b) => b.newestDate - a.newestDate);
            break;
        case 'count':
            tags.sort((a, b) => b.count - a.count);
            break;
    }

    return tags;
}

function renderTagEditorList() {
    const tags = getTagStats();

    tagEditorCount.textContent = `${tags.length} tag${tags.length === 1 ? '' : 's'}`;

    if (tags.length === 0) {
        tagEditorList.innerHTML = `
            <div class="tag-editor-empty">
                ${tagSearchQuery ? `No tags match "${tagSearchQuery}"` : 'No tags yet'}
            </div>
        `;
        return;
    }

    tagEditorList.innerHTML = tags.map(tag => `
        <div class="tag-editor-item" data-tag="${escapeHtml(tag.name)}">
            <div class="tag-editor-icon">🏷️</div>
            <div class="tag-editor-info">
                <div class="tag-editor-name">${escapeHtml(tag.name)}</div>
                <div class="tag-editor-count-label">${tag.count} item${tag.count === 1 ? '' : 's'}</div>
            </div>
            <button class="tag-editor-delete" title="Delete tag" onclick="deleteTag('${escapeHtml(tag.name).replace(/'/g, "\\'")}')">
                🗑️
            </button>
        </div>
    `).join('');
}

async function deleteTag(tagName) {
    if (!confirm(`Remove "${tagName}" from all items? This cannot be undone.`)) {
        return;
    }

    const itemsWithTag = allItems.filter(item => {
        const tags = item.analysis?.tags || [];
        return tags.includes(tagName);
    });

    try {
        for (const item of itemsWithTag) {
            const currentTags = [...(item.analysis?.tags || [])];
            const newTags = currentTags.filter(t => t !== tagName);

            const response = await fetch(`/api/items/${item.id}`, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${authToken}`
                },
                body: JSON.stringify({ tags: newTags })
            });

            if (!response.ok) {
                throw new Error(`Failed to update item ${item.id}`);
            }

            // Update local state
            if (item.analysis) {
                item.analysis.tags = newTags;
            }
        }

        alert(`Removed "${tagName}" from ${itemsWithTag.length} items`);
        renderTagEditorList();
        renderFilteredItems(); // Refresh main list
    } catch (error) {
        console.error('Error deleting tag:', error);
        alert('Failed to delete tag: ' + error.message);
    }
}

// Helper function for HTML escaping (if not already present)
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
```

3. Call setupTagEditor in the initialization (in the DOMContentLoaded or init section):
```javascript
setupTagEditor();
```

---

## Verification

**Flutter tests:**
```bash
cd flutter && flutter analyze
```

**Manual verification:**
- [ ] Flutter: Open user menu, tap "Tag Editor"
- [ ] Flutter: See list of tags with item counts
- [ ] Flutter: Search filters tags
- [ ] Flutter: Sort by Name/Newest/Most Used works
- [ ] Flutter: Delete tag shows confirmation
- [ ] Flutter: After delete, tag is removed from all items
- [ ] Flutter: Returning to main screen shows updated items
- [ ] Web: Open user menu, click "Tag Editor"
- [ ] Web: Modal shows with tag list
- [ ] Web: Search and sort work
- [ ] Web: Delete removes tag from items
- [ ] Web: Main list updates after deletion
