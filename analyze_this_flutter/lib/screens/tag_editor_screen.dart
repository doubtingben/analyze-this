import 'package:flutter/material.dart';
import '../models/history_item.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';

/// A helper class to store tag statistics.
class _TagStats {
  final String name;
  final int count;
  final DateTime newestItemDate;
  final List<HistoryItem> items;

  _TagStats({
    required this.name,
    required this.count,
    required this.newestItemDate,
    required this.items,
  });
}

/// Sort options for the tag list.
enum _TagSortOption {
  name,
  newest,
  count,
}

/// A screen for viewing and managing tags across all items.
class TagEditorScreen extends StatefulWidget {
  final String authToken;
  final List<HistoryItem> items;
  final void Function(List<HistoryItem> updatedItems)? onItemsUpdated;

  const TagEditorScreen({
    super.key,
    required this.authToken,
    required this.items,
    this.onItemsUpdated,
  });

  @override
  State<TagEditorScreen> createState() => _TagEditorScreenState();
}

class _TagEditorScreenState extends State<TagEditorScreen> {
  final ApiService _apiService = ApiService();
  final TextEditingController _searchController = TextEditingController();

  List<HistoryItem> _items = [];
  List<_TagStats> _allTags = [];
  List<_TagStats> _filteredTags = [];
  _TagSortOption _sortOption = _TagSortOption.count;
  String _searchQuery = '';
  bool _isDeleting = false;
  String? _deletingTag;

  @override
  void initState() {
    super.initState();
    _items = List.from(widget.items);
    _computeTagStats();
    _searchController.addListener(_onSearchChanged);
  }

  @override
  void dispose() {
    _searchController.removeListener(_onSearchChanged);
    _searchController.dispose();
    super.dispose();
  }

  void _onSearchChanged() {
    setState(() {
      _searchQuery = _searchController.text.toLowerCase();
      _filterAndSortTags();
    });
  }

  /// Extract tags from all items and compute statistics.
  void _computeTagStats() {
    final tagMap = <String, _TagStats>{};

    for (final item in _items) {
      final tags = _getTagsFromItem(item);
      final itemDate = DateTime.fromMillisecondsSinceEpoch(item.timestamp);

      for (final tag in tags) {
        if (tagMap.containsKey(tag)) {
          final existing = tagMap[tag]!;
          tagMap[tag] = _TagStats(
            name: tag,
            count: existing.count + 1,
            newestItemDate: itemDate.isAfter(existing.newestItemDate)
                ? itemDate
                : existing.newestItemDate,
            items: [...existing.items, item],
          );
        } else {
          tagMap[tag] = _TagStats(
            name: tag,
            count: 1,
            newestItemDate: itemDate,
            items: [item],
          );
        }
      }
    }

    _allTags = tagMap.values.toList();
    _filterAndSortTags();
  }

  /// Get tags from an item's analysis field.
  List<String> _getTagsFromItem(HistoryItem item) {
    final analysis = item.analysis;
    if (analysis == null) return [];

    final tags = analysis['tags'];
    if (tags == null) return [];

    if (tags is List) {
      return tags.map((t) => t.toString()).toList();
    }

    return [];
  }

  /// Filter and sort tags based on current search query and sort option.
  void _filterAndSortTags() {
    // Filter by search query
    if (_searchQuery.isEmpty) {
      _filteredTags = List.from(_allTags);
    } else {
      _filteredTags = _allTags
          .where((tag) => tag.name.toLowerCase().contains(_searchQuery))
          .toList();
    }

    // Sort
    switch (_sortOption) {
      case _TagSortOption.name:
        _filteredTags.sort(
            (a, b) => a.name.toLowerCase().compareTo(b.name.toLowerCase()));
        break;
      case _TagSortOption.newest:
        _filteredTags
            .sort((a, b) => b.newestItemDate.compareTo(a.newestItemDate));
        break;
      case _TagSortOption.count:
        _filteredTags.sort((a, b) => b.count.compareTo(a.count));
        break;
    }
  }

  /// Show confirmation dialog and delete a tag from all items.
  Future<void> _confirmDeleteTag(_TagStats tagStats) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Tag'),
        content: Text(
          'Are you sure you want to remove the tag "${tagStats.name}" from ${tagStats.count} item${tagStats.count == 1 ? '' : 's'}?\n\nThis action cannot be undone.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: FilledButton.styleFrom(
              backgroundColor: AppColors.error,
            ),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      await _deleteTag(tagStats);
    }
  }

  /// Delete a tag from all items that have it.
  Future<void> _deleteTag(_TagStats tagStats) async {
    setState(() {
      _isDeleting = true;
      _deletingTag = tagStats.name;
    });

    try {
      // Update each item that has this tag
      for (final item in tagStats.items) {
        final currentTags = _getTagsFromItem(item);
        final newTags = currentTags.where((t) => t != tagStats.name).toList();

        // Call API to update the item
        await _apiService.updateItem(
          widget.authToken,
          item.id,
          tags: newTags,
        );

        // Update local item
        final itemIndex = _items.indexWhere((i) => i.id == item.id);
        if (itemIndex != -1) {
          final existingAnalysis =
              Map<String, dynamic>.from(_items[itemIndex].analysis ?? {});
          existingAnalysis['tags'] = newTags;
          _items[itemIndex] = _items[itemIndex].copyWith(
            analysis: existingAnalysis,
          );
        }
      }

      // Recompute tag stats
      _computeTagStats();

      // Notify parent of updated items
      widget.onItemsUpdated?.call(_items);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
                'Removed "${tagStats.name}" from ${tagStats.count} item${tagStats.count == 1 ? '' : 's'}'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to delete tag: $e'),
            backgroundColor: AppColors.error,
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isDeleting = false;
          _deletingTag = null;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Manage Tags'),
        actions: [
          PopupMenuButton<_TagSortOption>(
            icon: const Icon(Icons.sort),
            tooltip: 'Sort by',
            onSelected: (option) {
              setState(() {
                _sortOption = option;
                _filterAndSortTags();
              });
            },
            itemBuilder: (context) => [
              PopupMenuItem(
                value: _TagSortOption.name,
                child: Row(
                  children: [
                    Icon(
                      Icons.sort_by_alpha,
                      color: _sortOption == _TagSortOption.name
                          ? AppColors.primary
                          : null,
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Text(
                      'Name',
                      style: TextStyle(
                        color: _sortOption == _TagSortOption.name
                            ? AppColors.primary
                            : null,
                        fontWeight: _sortOption == _TagSortOption.name
                            ? FontWeight.bold
                            : null,
                      ),
                    ),
                  ],
                ),
              ),
              PopupMenuItem(
                value: _TagSortOption.newest,
                child: Row(
                  children: [
                    Icon(
                      Icons.schedule,
                      color: _sortOption == _TagSortOption.newest
                          ? AppColors.primary
                          : null,
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Text(
                      'Newest',
                      style: TextStyle(
                        color: _sortOption == _TagSortOption.newest
                            ? AppColors.primary
                            : null,
                        fontWeight: _sortOption == _TagSortOption.newest
                            ? FontWeight.bold
                            : null,
                      ),
                    ),
                  ],
                ),
              ),
              PopupMenuItem(
                value: _TagSortOption.count,
                child: Row(
                  children: [
                    Icon(
                      Icons.tag,
                      color: _sortOption == _TagSortOption.count
                          ? AppColors.primary
                          : null,
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Text(
                      'Most Used',
                      style: TextStyle(
                        color: _sortOption == _TagSortOption.count
                            ? AppColors.primary
                            : null,
                        fontWeight: _sortOption == _TagSortOption.count
                            ? FontWeight.bold
                            : null,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: Column(
        children: [
          // Search field
          Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
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
                        },
                      )
                    : null,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                filled: true,
                fillColor: AppColors.surface,
              ),
            ),
          ),

          // Tag count summary
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
            child: Row(
              children: [
                Text(
                  _searchQuery.isEmpty
                      ? '${_allTags.length} tag${_allTags.length == 1 ? '' : 's'}'
                      : '${_filteredTags.length} of ${_allTags.length} tag${_allTags.length == 1 ? '' : 's'}',
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
            child: _buildTagList(),
          ),
        ],
      ),
    );
  }

  Widget _buildTagList() {
    // Empty state - no tags at all
    if (_allTags.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.label_off_outlined,
                size: 64,
                color: AppColors.textSecondary.withValues(alpha: 0.5),
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(
                'No Tags',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: AppColors.textSecondary,
                    ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'Tags will appear here once items have been analyzed.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppColors.textSecondary,
                    ),
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      );
    }

    // Empty state - no search matches
    if (_filteredTags.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.search_off,
                size: 64,
                color: AppColors.textSecondary.withValues(alpha: 0.5),
              ),
              const SizedBox(height: AppSpacing.lg),
              Text(
                'No Matches',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: AppColors.textSecondary,
                    ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                'No tags match "$_searchQuery".',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: AppColors.textSecondary,
                    ),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.lg),
              TextButton(
                onPressed: () {
                  _searchController.clear();
                },
                child: const Text('Clear search'),
              ),
            ],
          ),
        ),
      );
    }

    // Tag list
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
      itemCount: _filteredTags.length,
      itemBuilder: (context, index) {
        final tagStats = _filteredTags[index];
        final isDeleting = _isDeleting && _deletingTag == tagStats.name;

        return Card(
          margin: const EdgeInsets.only(bottom: AppSpacing.sm),
          child: ListTile(
            leading: Container(
              padding: const EdgeInsets.all(AppSpacing.sm),
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Icon(
                Icons.label_outline,
                color: AppColors.primary,
              ),
            ),
            title: Text(
              tagStats.name,
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
            subtitle: Text(
              '${tagStats.count} item${tagStats.count == 1 ? '' : 's'}',
              style: TextStyle(
                color: AppColors.textSecondary,
                fontSize: 12,
              ),
            ),
            trailing: isDeleting
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : IconButton(
                    icon: Icon(
                      Icons.delete_outline,
                      color: AppColors.error,
                    ),
                    onPressed:
                        _isDeleting ? null : () => _confirmDeleteTag(tagStats),
                    tooltip: 'Delete tag',
                  ),
          ),
        );
      },
    );
  }
}
