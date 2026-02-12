import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:image_picker/image_picker.dart';
import '../models/history_item.dart';
import '../models/item_note.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../widgets/type_badge.dart';

class ItemDetailScreen extends StatefulWidget {
  final List<HistoryItem> items;
  final int initialIndex;
  final String? authToken;
  final Function(HistoryItem updatedItem)? onItemUpdated;
  final Function(HistoryItem deletedItem)? onItemDeleted;

  const ItemDetailScreen({
    super.key,
    required this.items,
    required this.initialIndex,
    this.authToken,
    this.onItemUpdated,
    this.onItemDeleted,
  });

  @override
  State<ItemDetailScreen> createState() => _ItemDetailScreenState();
}

class _ItemDetailScreenState extends State<ItemDetailScreen> {
  late PageController _pageController;
  late int _currentIndex;
  late List<HistoryItem> _items;
  bool _isEditMode = false;
  bool _isDeleting = false;
  final ApiService _apiService = ApiService();

  @override
  void initState() {
    super.initState();
    _currentIndex = widget.initialIndex;
    _items = List.from(widget.items);
    _pageController = PageController(initialPage: widget.initialIndex);
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  HistoryItem get _currentItem => _items[_currentIndex];

  void _toggleEditMode() {
    setState(() {
      _isEditMode = !_isEditMode;
    });
  }

  void _handleItemUpdated(HistoryItem updatedItem) {
    setState(() {
      _items[_currentIndex] = updatedItem;
    });
    widget.onItemUpdated?.call(updatedItem);
  }

  Future<void> _confirmAndDeleteItem() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Item'),
        content: const Text('Are you sure you want to delete this item? This action cannot be undone.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed != true || widget.authToken == null) return;

    setState(() {
      _isDeleting = true;
    });

    try {
      await _apiService.deleteItem(widget.authToken!, _currentItem.id);

      final deletedItem = _currentItem;
      widget.onItemDeleted?.call(deletedItem);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Item deleted')),
        );
        Navigator.of(context).pop();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isDeleting = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_currentItem.title ?? 'Item Details'),
        actions: [
          // Edit button
          IconButton(
            icon: Icon(_isEditMode ? Icons.close : Icons.edit),
            onPressed: _isDeleting ? null : _toggleEditMode,
            tooltip: _isEditMode ? 'Cancel editing' : 'Edit item',
          ),
          // Delete button
          _isDeleting
              ? const Padding(
                  padding: EdgeInsets.all(12),
                  child: SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: AppColors.error,
                    ),
                  ),
                )
              : IconButton(
                  icon: const Icon(Icons.delete_outline),
                  onPressed: _confirmAndDeleteItem,
                  tooltip: 'Delete item',
                  color: AppColors.error,
                ),
          // Page indicator
          Center(
            child: Padding(
              padding: const EdgeInsets.only(right: AppSpacing.lg),
              child: Text(
                '${_currentIndex + 1} / ${_items.length}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ),
        ],
      ),
      body: PageView.builder(
        controller: _pageController,
        itemCount: _items.length,
        physics: _isEditMode ? const NeverScrollableScrollPhysics() : null,
        onPageChanged: (index) {
          setState(() {
            _currentIndex = index;
            // Exit edit mode when swiping to a new page
            _isEditMode = false;
          });
        },
        itemBuilder: (context, index) {
          return _ItemDetailPage(
            item: _items[index],
            authToken: widget.authToken,
            isEditMode: _isEditMode && index == _currentIndex,
            onItemUpdated: _handleItemUpdated,
            onEditModeChanged: (isEdit) {
              setState(() {
                _isEditMode = isEdit;
              });
            },
          );
        },
      ),
    );
  }
}

class _ItemDetailPage extends StatefulWidget {
  final HistoryItem item;
  final String? authToken;
  final bool isEditMode;
  final Function(HistoryItem updatedItem)? onItemUpdated;
  final Function(bool isEdit)? onEditModeChanged;

  const _ItemDetailPage({
    required this.item,
    this.authToken,
    this.isEditMode = false,
    this.onItemUpdated,
    this.onEditModeChanged,
  });

  @override
  State<_ItemDetailPage> createState() => _ItemDetailPageState();
}

class _ItemDetailPageState extends State<_ItemDetailPage> {
  late TextEditingController _titleController;
  late List<String> _editableTags;
  List<ItemNote> _notes = [];
  bool _isLoadingNotes = false;
  bool _isSaving = false;
  final ApiService _apiService = ApiService();
  final ImagePicker _imagePicker = ImagePicker();

  // Timeline state
  bool _isTimelineExpanded = false;
  late TextEditingController _timelineDateController;
  late TextEditingController _timelineTimeController;
  late TextEditingController _timelineDurationController;
  late TextEditingController _timelinePrincipalController;
  late TextEditingController _timelineLocationController;
  late TextEditingController _timelinePurposeController;

  bool get _hasAnalysis =>
      widget.item.analysis != null && widget.item.analysis!.isNotEmpty;
  bool get _isImageType =>
      widget.item.type == 'image' || widget.item.type == 'screenshot';
  bool get _isUrlType => widget.item.type == 'web_url';

  @override
  void initState() {
    super.initState();
    _titleController = TextEditingController(text: widget.item.title ?? '');
    _editableTags = _getTagsFromAnalysis();
    _initTimelineControllers();
    _loadNotes();
  }

  void _initTimelineControllers() {
    final timeline = _getTimelineFromAnalysis();
    _timelineDateController = TextEditingController(text: timeline['date'] ?? '');
    _timelineTimeController = TextEditingController(text: timeline['time'] ?? '');
    _timelineDurationController = TextEditingController(text: timeline['duration'] ?? '');
    _timelinePrincipalController = TextEditingController(text: timeline['principal'] ?? '');
    _timelineLocationController = TextEditingController(text: timeline['location'] ?? '');
    _timelinePurposeController = TextEditingController(text: timeline['purpose'] ?? '');
  }

  Map<String, String?> _getTimelineFromAnalysis() {
    final analysis = widget.item.analysis;
    if (analysis == null) return {};
    final timeline = analysis['timeline'];
    if (timeline == null || timeline is! Map) return {};
    return {
      'date': timeline['date']?.toString(),
      'time': timeline['time']?.toString(),
      'duration': timeline['duration']?.toString(),
      'principal': timeline['principal']?.toString(),
      'location': timeline['location']?.toString(),
      'purpose': timeline['purpose']?.toString(),
    };
  }

  bool get _hasTimeline {
    final timeline = _getTimelineFromAnalysis();
    return timeline.values.any((v) => v != null && v.isNotEmpty);
  }

  @override
  void didUpdateWidget(_ItemDetailPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.item.id != widget.item.id) {
      _titleController.text = widget.item.title ?? '';
      _editableTags = _getTagsFromAnalysis();
      _resetTimelineControllers();
      _loadNotes();
    }
    // If exiting edit mode without saving, reset values
    if (oldWidget.isEditMode && !widget.isEditMode) {
      _titleController.text = widget.item.title ?? '';
      _editableTags = _getTagsFromAnalysis();
      _resetTimelineControllers();
    }
  }

  void _resetTimelineControllers() {
    final timeline = _getTimelineFromAnalysis();
    _timelineDateController.text = timeline['date'] ?? '';
    _timelineTimeController.text = timeline['time'] ?? '';
    _timelineDurationController.text = timeline['duration'] ?? '';
    _timelinePrincipalController.text = timeline['principal'] ?? '';
    _timelineLocationController.text = timeline['location'] ?? '';
    _timelinePurposeController.text = timeline['purpose'] ?? '';
  }

  @override
  void dispose() {
    _titleController.dispose();
    _timelineDateController.dispose();
    _timelineTimeController.dispose();
    _timelineDurationController.dispose();
    _timelinePrincipalController.dispose();
    _timelineLocationController.dispose();
    _timelinePurposeController.dispose();
    super.dispose();
  }

  List<String> _getTagsFromAnalysis() {
    final analysis = widget.item.analysis;
    if (analysis == null) return [];
    final tags = analysis['tags'];
    if (tags == null || tags is! List) return [];
    return tags.map((t) => t.toString()).toList();
  }

  Future<void> _loadNotes() async {
    if (widget.authToken == null) return;

    setState(() {
      _isLoadingNotes = true;
    });

    try {
      final notes =
          await _apiService.getItemNotes(widget.authToken!, widget.item.id);
      if (mounted) {
        setState(() {
          _notes = notes;
          _isLoadingNotes = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isLoadingNotes = false;
        });
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load notes: $e')),
        );
      }
    }
  }

  Future<void> _saveChanges() async {
    if (widget.authToken == null) return;

    final newTitle = _titleController.text.trim();
    final currentTimeline = _getTimelineFromAnalysis();
    final newTimeline = _buildTimelinePayload();

    final hasChanges = newTitle != (widget.item.title ?? '') ||
        !_listEquals(_editableTags, _getTagsFromAnalysis()) ||
        _hasTimelineChanges(currentTimeline, newTimeline);

    if (!hasChanges) {
      widget.onEditModeChanged?.call(false);
      return;
    }

    setState(() {
      _isSaving = true;
    });

    try {
      await _apiService.updateItem(
        widget.authToken!,
        widget.item.id,
        title: newTitle.isNotEmpty ? newTitle : null,
        tags: _editableTags,
        timeline: newTimeline.isNotEmpty ? newTimeline : null,
      );

      // Update the item locally
      final updatedAnalysis =
          Map<String, dynamic>.from(widget.item.analysis ?? {});
      updatedAnalysis['tags'] = _editableTags;

      // Update timeline in local analysis
      if (newTimeline.isNotEmpty) {
        updatedAnalysis['timeline'] = newTimeline;
      }

      final updatedItem = widget.item.copyWith(
        title: newTitle.isNotEmpty ? newTitle : widget.item.title,
        analysis: updatedAnalysis,
      );

      widget.onItemUpdated?.call(updatedItem);
      widget.onEditModeChanged?.call(false);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Changes saved')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to save: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() {
          _isSaving = false;
        });
      }
    }
  }

  Map<String, String?> _buildTimelinePayload() {
    final result = <String, String?>{};
    final date = _timelineDateController.text.trim();
    final time = _timelineTimeController.text.trim();
    final duration = _timelineDurationController.text.trim();
    final principal = _timelinePrincipalController.text.trim();
    final location = _timelineLocationController.text.trim();
    final purpose = _timelinePurposeController.text.trim();

    if (date.isNotEmpty) result['date'] = date;
    if (time.isNotEmpty) result['time'] = time;
    if (duration.isNotEmpty) result['duration'] = duration;
    if (principal.isNotEmpty) result['principal'] = principal;
    if (location.isNotEmpty) result['location'] = location;
    if (purpose.isNotEmpty) result['purpose'] = purpose;

    return result;
  }

  bool _hasTimelineChanges(Map<String, String?> current, Map<String, String?> updated) {
    const fields = ['date', 'time', 'duration', 'principal', 'location', 'purpose'];
    for (final field in fields) {
      final currentVal = current[field] ?? '';
      final updatedVal = updated[field] ?? '';
      if (currentVal != updatedVal) return true;
    }
    return false;
  }

  bool _listEquals(List<String> a, List<String> b) {
    if (a.length != b.length) return false;
    for (int i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  void _addTag(String tag) {
    if (tag.isNotEmpty && !_editableTags.contains(tag)) {
      setState(() {
        _editableTags.add(tag);
      });
    }
  }

  void _removeTag(String tag) {
    setState(() {
      _editableTags.remove(tag);
    });
  }

  Future<void> _showAddTagDialog() async {
    final controller = TextEditingController();
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add Tag'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'Enter tag name',
            border: OutlineInputBorder(),
          ),
          onSubmitted: (value) => Navigator.of(context).pop(value),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(controller.text),
            child: const Text('Add'),
          ),
        ],
      ),
    );

    if (result != null && result.trim().isNotEmpty) {
      _addTag(result.trim());
    }
    controller.dispose();
  }

  Future<void> _createNote({String? text, String? imagePath, String noteType = 'context'}) async {
    if (widget.authToken == null) return;
    if (text == null && imagePath == null) return;

    try {
      final note = await _apiService.createNote(
        widget.authToken!,
        widget.item.id,
        text: text,
        imagePath: imagePath,
        noteType: noteType,
      );

      setState(() {
        _notes.insert(0, note);
      });

      // Update note count on the item
      final updatedItem =
          widget.item.copyWith(noteCount: widget.item.noteCount + 1);
      widget.onItemUpdated?.call(updatedItem);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Note added')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to add note: $e')),
        );
      }
    }
  }

  Future<void> _deleteNote(ItemNote note) async {
    if (widget.authToken == null) return;

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Note'),
        content: const Text('Are you sure you want to delete this note?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    try {
      await _apiService.deleteNote(widget.authToken!, note.id);

      setState(() {
        _notes.removeWhere((n) => n.id == note.id);
      });

      // Update note count on the item
      final updatedItem = widget.item
          .copyWith(noteCount: (widget.item.noteCount - 1).clamp(0, 999));
      widget.onItemUpdated?.call(updatedItem);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Note deleted')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete note: $e')),
        );
      }
    }
  }

  Future<void> _editNote(ItemNote note) async {
    final controller = TextEditingController(text: note.text ?? '');

    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Edit Note'),
        content: TextField(
          controller: controller,
          maxLines: 4,
          decoration: const InputDecoration(
            hintText: 'Edit your note...',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(controller.text),
            child: const Text('Save'),
          ),
        ],
      ),
    );

    controller.dispose();

    if (result == null || result.trim().isEmpty) return;

    try {
      await _apiService.updateNote(
        widget.authToken!,
        note.id,
        text: result.trim(),
      );

      setState(() {
        final index = _notes.indexWhere((n) => n.id == note.id);
        if (index != -1) {
          _notes[index] = note.copyWith(
            text: result.trim(),
            updatedAt: DateTime.now(),
          );
        }
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Note updated')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to update note: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final dateStr = DateFormat.yMMMd().add_jm().format(
          DateTime.fromMillisecondsSinceEpoch(widget.item.timestamp),
        );

    return Column(
      children: [
        // Scrollable content
        Expanded(
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Media preview
                if (_isImageType && widget.item.value.isNotEmpty)
                  _buildImagePreview(),

                // Content section
                Padding(
                  padding: const EdgeInsets.all(AppSpacing.lg),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // Type badge and date
                      Row(
                        children: [
                          TypeBadge(type: widget.item.type),
                          const SizedBox(width: AppSpacing.md),
                          Text(dateStr, style: theme.textTheme.bodySmall),
                        ],
                      ),
                      const SizedBox(height: AppSpacing.lg),

                      // Title (editable or static)
                      _buildEditableTitle(context),

                      // Content/Value
                      _buildContentSection(context),

                      // Metadata section
                      if (widget.item.metadata != null) ...[
                        const SizedBox(height: AppSpacing.xl),
                        _buildMetadataSection(context),
                      ],

                      // Analysis section (with editable tags)
                      if (_hasAnalysis || widget.isEditMode) ...[
                        const SizedBox(height: AppSpacing.xl),
                        _buildAnalysisSection(context),
                      ],

                      // Timeline section (collapsible, editable)
                      _buildTimelineSection(context),

                      // Follow-up section (if available)
                      _buildFollowUpSection(context),

                      // Notes section
                      const SizedBox(height: AppSpacing.xl),
                      _buildNotesSection(context),

                      // Item ID (readonly)
                      const SizedBox(height: AppSpacing.xl),
                      _buildItemIdSection(context),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),

        // Fixed bottom bar for edit mode
        if (widget.isEditMode)
          Container(
            padding: const EdgeInsets.all(AppSpacing.lg),
            decoration: BoxDecoration(
              color: theme.scaffoldBackgroundColor,
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.1),
                  blurRadius: 8,
                  offset: const Offset(0, -2),
                ),
              ],
            ),
            child: SafeArea(
              top: false,
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _isSaving
                          ? null
                          : () => widget.onEditModeChanged?.call(false),
                      child: const Text('Cancel'),
                    ),
                  ),
                  const SizedBox(width: AppSpacing.md),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _isSaving ? null : _saveChanges,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppColors.primary,
                        foregroundColor: Colors.white,
                      ),
                      child: _isSaving
                          ? const SizedBox(
                              height: 20,
                              width: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Text('Save'),
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildImagePreview() {
    return AspectRatio(
      aspectRatio: 4 / 3,
      child: CachedNetworkImage(
        imageUrl: widget.item.value,
        httpHeaders: widget.authToken != null
            ? {'Authorization': 'Bearer ${widget.authToken}'}
            : null,
        fit: BoxFit.contain,
        placeholder: (context, url) => Container(
          color: AppColors.badgeBackground,
          child: const Center(
            child: CircularProgressIndicator(
              strokeWidth: 2,
              color: AppColors.primary,
            ),
          ),
        ),
        errorWidget: (context, url, error) => Container(
          color: AppColors.badgeBackground,
          child: const Center(
            child: Icon(
              Icons.broken_image_outlined,
              color: AppColors.textSecondary,
              size: 48,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildEditableTitle(BuildContext context) {
    final theme = Theme.of(context);

    if (widget.isEditMode) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Title',
            style: theme.textTheme.bodySmall
                ?.copyWith(fontWeight: FontWeight.w500),
          ),
          const SizedBox(height: AppSpacing.sm),
          TextField(
            controller: _titleController,
            style: theme.textTheme.titleLarge,
            decoration: InputDecoration(
              hintText: 'Enter title',
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
              ),
              contentPadding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.sm,
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
        ],
      );
    }

    if (widget.item.title != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.item.title!,
            style: theme.textTheme.titleLarge,
          ),
          const SizedBox(height: AppSpacing.md),
        ],
      );
    }

    return const SizedBox.shrink();
  }

  Widget _buildContentSection(BuildContext context) {
    final theme = Theme.of(context);

    if (_isUrlType) {
      return InkWell(
        onTap: () => _launchUrl(widget.item.value),
        child: Container(
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            color: AppColors.primary.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            children: [
              const Icon(Icons.link, color: AppColors.primary),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Text(
                  widget.item.value,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: AppColors.primary,
                    decoration: TextDecoration.underline,
                  ),
                ),
              ),
              const Icon(Icons.open_in_new, color: AppColors.primary, size: 18),
            ],
          ),
        ),
      );
    }

    // Text content
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Content', style: theme.textTheme.titleMedium),
        const SizedBox(height: AppSpacing.sm),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            color: AppColors.badgeBackground,
            borderRadius: BorderRadius.circular(8),
          ),
          child: SelectableText(
            widget.item.value,
            style: theme.textTheme.bodyMedium,
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton.icon(
            onPressed: () => _copyToClipboard(context, widget.item.value),
            icon: const Icon(Icons.copy, size: 16),
            label: const Text('Copy'),
          ),
        ),
      ],
    );
  }

  Widget _buildMetadataSection(BuildContext context) {
    final theme = Theme.of(context);
    final meta = widget.item.metadata!;
    final entries = <MapEntry<String, String>>[];

    if (meta.fileName != null) {
      entries.add(MapEntry('File Name', meta.fileName!));
    }
    if (meta.mimeType != null) {
      entries.add(MapEntry('Type', meta.mimeType!));
    }
    if (meta.fileSize != null) {
      entries.add(MapEntry('Size', _formatFileSize(meta.fileSize!)));
    }
    if (meta.width != null && meta.height != null) {
      entries.add(MapEntry('Dimensions', '${meta.width} x ${meta.height}'));
    }
    if (meta.duration != null) {
      entries.add(MapEntry('Duration', _formatDuration(meta.duration!)));
    }

    if (entries.isEmpty) return const SizedBox.shrink();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Metadata', style: theme.textTheme.titleMedium),
        const SizedBox(height: AppSpacing.md),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            color: AppColors.badgeBackground,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Column(
            children: entries
                .map((e) => Padding(
                      padding:
                          const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          SizedBox(
                            width: 100,
                            child: Text(
                              e.key,
                              style: theme.textTheme.bodySmall?.copyWith(
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                          Expanded(
                            child: Text(
                              e.value,
                              style: theme.textTheme.bodyMedium,
                            ),
                          ),
                        ],
                      ),
                    ))
                .toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildAnalysisSection(BuildContext context) {
    final theme = Theme.of(context);
    final analysis = widget.item.analysis ?? {};

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('Analysis', style: theme.textTheme.titleMedium),
            const SizedBox(width: AppSpacing.sm),
            const Text('', style: TextStyle(fontSize: 18)),
          ],
        ),
        const SizedBox(height: AppSpacing.md),

        // Overview
        if (analysis['overview'] != null) ...[
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AppSpacing.md),
            decoration: BoxDecoration(
              color: AppColors.primary.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              analysis['overview'] as String,
              style: theme.textTheme.bodyMedium,
            ),
          ),
          const SizedBox(height: AppSpacing.md),
        ],

        // Tags (editable or static)
        _buildEditableTags(context),
      ],
    );
  }

  Widget _buildEditableTags(BuildContext context) {
    final theme = Theme.of(context);
    final tags = widget.isEditMode ? _editableTags : _getTagsFromAnalysis();

    if (!widget.isEditMode && tags.isEmpty) {
      return const SizedBox.shrink();
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Tags',
          style:
              theme.textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w500),
        ),
        const SizedBox(height: AppSpacing.sm),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: [
            ...tags.map((tag) => widget.isEditMode
                ? Chip(
                    label: Text(tag),
                    deleteIcon: const Icon(Icons.close, size: 16),
                    onDeleted: () => _removeTag(tag),
                    backgroundColor: AppColors.badgeBackground,
                    labelStyle: theme.textTheme.labelMedium,
                  )
                : Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.sm,
                      vertical: AppSpacing.xs,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.badgeBackground,
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      tag,
                      style: theme.textTheme.labelMedium,
                    ),
                  )),
            if (widget.isEditMode)
              ActionChip(
                avatar: const Icon(Icons.add, size: 16),
                label: const Text('Add'),
                onPressed: _showAddTagDialog,
              ),
          ],
        ),
      ],
    );
  }

  Widget _buildFollowUpSection(BuildContext context) {
    final theme = Theme.of(context);
    final followUp = widget.item.analysis?['follow_up'] as String?;

    if (followUp == null || followUp.isEmpty) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('🚩', style: TextStyle(fontSize: 16)),
              const SizedBox(width: AppSpacing.sm),
              Text('Follow-up', style: theme.textTheme.titleMedium),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.delete_outline),
                iconSize: 20,
                color: AppColors.error,
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
                onPressed: () => _confirmDeleteFollowUp(context),
                tooltip: 'Delete follow-up',
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AppSpacing.md),
            decoration: BoxDecoration(
              color: AppColors.badgeBackground,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: AppColors.textSecondary.withValues(alpha: 0.2),
              ),
            ),
            child: Text(
              followUp,
              style: theme.textTheme.bodyMedium,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTimelineSection(BuildContext context) {
    final theme = Theme.of(context);
    final hasData = _hasTimeline;

    // Only show if there's data or we're in edit mode
    if (!hasData && !widget.isEditMode) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.only(top: AppSpacing.xl),
      child: Theme(
        data: theme.copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          key: PageStorageKey('timeline_${widget.item.id}'),
          initiallyExpanded: _isTimelineExpanded,
          onExpansionChanged: (expanded) {
            setState(() => _isTimelineExpanded = expanded);
          },
          tilePadding: EdgeInsets.zero,
          childrenPadding: const EdgeInsets.only(top: AppSpacing.sm),
          title: Row(
            children: [
              const Text('📅', style: TextStyle(fontSize: 16)),
              const SizedBox(width: AppSpacing.sm),
              Text('Timeline', style: theme.textTheme.titleMedium),
              if (hasData) ...[
                const SizedBox(width: AppSpacing.sm),
                Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.sm,
                    vertical: 2,
                  ),
                  decoration: BoxDecoration(
                    color: AppColors.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    _countTimelineFields().toString(),
                    style: theme.textTheme.labelSmall?.copyWith(
                      color: AppColors.primary,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ],
          ),
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: AppColors.badgeBackground,
                borderRadius: BorderRadius.circular(8),
              ),
              child: widget.isEditMode
                  ? _buildEditableTimelineFields(context)
                  : _buildReadonlyTimelineFields(context),
            ),
          ],
        ),
      ),
    );
  }

  int _countTimelineFields() {
    final timeline = _getTimelineFromAnalysis();
    return timeline.values.where((v) => v != null && v.isNotEmpty).length;
  }

  Widget _buildReadonlyTimelineFields(BuildContext context) {
    final theme = Theme.of(context);
    final timeline = _getTimelineFromAnalysis();

    final fields = <MapEntry<String, String>>[];
    if (timeline['date']?.isNotEmpty == true) {
      fields.add(MapEntry('Date', timeline['date']!));
    }
    if (timeline['time']?.isNotEmpty == true) {
      fields.add(MapEntry('Time', timeline['time']!));
    }
    if (timeline['duration']?.isNotEmpty == true) {
      fields.add(MapEntry('Duration', timeline['duration']!));
    }
    if (timeline['principal']?.isNotEmpty == true) {
      fields.add(MapEntry('Principal', timeline['principal']!));
    }
    if (timeline['location']?.isNotEmpty == true) {
      fields.add(MapEntry('Location', timeline['location']!));
    }
    if (timeline['purpose']?.isNotEmpty == true) {
      fields.add(MapEntry('Purpose', timeline['purpose']!));
    }

    return Column(
      children: fields
          .map((e) => Padding(
                padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    SizedBox(
                      width: 80,
                      child: Text(
                        e.key,
                        style: theme.textTheme.bodySmall?.copyWith(
                          fontWeight: FontWeight.w500,
                          color: AppColors.textSecondary,
                        ),
                      ),
                    ),
                    Expanded(
                      child: Text(
                        e.value,
                        style: theme.textTheme.bodyMedium,
                      ),
                    ),
                  ],
                ),
              ))
          .toList(),
    );
  }

  Widget _buildEditableTimelineFields(BuildContext context) {
    return Column(
      children: [
        _buildTimelineTextField(
          controller: _timelineDateController,
          label: 'Date',
          hint: 'YYYY-MM-DD',
        ),
        const SizedBox(height: AppSpacing.md),
        _buildTimelineTextField(
          controller: _timelineTimeController,
          label: 'Time',
          hint: 'HH:MM:SS',
        ),
        const SizedBox(height: AppSpacing.md),
        _buildTimelineTextField(
          controller: _timelineDurationController,
          label: 'Duration',
          hint: 'HH:MM:SS',
        ),
        const SizedBox(height: AppSpacing.md),
        _buildTimelineTextField(
          controller: _timelinePrincipalController,
          label: 'Principal',
          hint: 'Person or organization',
        ),
        const SizedBox(height: AppSpacing.md),
        _buildTimelineTextField(
          controller: _timelineLocationController,
          label: 'Location',
          hint: 'Where it takes place',
        ),
        const SizedBox(height: AppSpacing.md),
        _buildTimelineTextField(
          controller: _timelinePurposeController,
          label: 'Purpose',
          hint: 'What the event is about',
          maxLines: 2,
        ),
      ],
    );
  }

  Widget _buildTimelineTextField({
    required TextEditingController controller,
    required String label,
    required String hint,
    int maxLines = 1,
  }) {
    return TextField(
      controller: controller,
      maxLines: maxLines,
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        border: const OutlineInputBorder(),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.md,
          vertical: AppSpacing.sm,
        ),
      ),
    );
  }

  Future<void> _confirmDeleteFollowUp(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete Follow-up'),
        content: const Text(
          'This will remove the follow-up and mark the item as processed. Continue?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      await _deleteFollowUp();
    }
  }

  Future<void> _deleteFollowUp() async {
    if (widget.authToken == null) return;

    setState(() => _isSaving = true);

    try {
      await _apiService.updateItem(
        widget.authToken!,
        widget.item.id,
        status: 'processed',
        nextStep: 'none',
        followUp: '',  // Empty string clears the follow_up
      );

      // Update the local item state
      final updatedAnalysis = Map<String, dynamic>.from(widget.item.analysis ?? {});
      updatedAnalysis.remove('follow_up');

      final updatedItem = widget.item.copyWith(
        status: 'processed',
        nextStep: 'none',
        analysis: updatedAnalysis,
      );

      widget.onItemUpdated?.call(updatedItem);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Follow-up deleted')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete follow-up: $e')),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isSaving = false);
      }
    }
  }

  Widget _buildNotesSection(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Text('Notes', style: theme.textTheme.titleMedium),
                if (_notes.isNotEmpty) ...[
                  const SizedBox(width: AppSpacing.sm),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.sm,
                      vertical: 2,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      '${_notes.length}',
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: AppColors.primary,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ],
              ],
            ),
            IconButton(
              icon: const Icon(Icons.add),
              onPressed: () async {
                final result = await showModalBottomSheet<Map<String, dynamic>>(
                  context: context,
                  isScrollControlled: true,
                  shape: const RoundedRectangleBorder(
                    borderRadius:
                        BorderRadius.vertical(top: Radius.circular(16)),
                  ),
                  builder: (context) => _AddNoteBottomSheet(
                    imagePicker: _imagePicker,
                  ),
                );

                if (result != null) {
                  await _createNote(
                    text: result['text'] as String?,
                    imagePath: result['imagePath'] as String?,
                    noteType: result['noteType'] as String? ?? 'context',
                  );
                }
              },
              tooltip: 'Add note',
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),

        if (_isLoadingNotes)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(AppSpacing.lg),
              child: CircularProgressIndicator(strokeWidth: 2),
            ),
          )
        else if (_notes.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(AppSpacing.xl),
            decoration: BoxDecoration(
              color: AppColors.badgeBackground,
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              children: [
                Icon(
                  Icons.note_add_outlined,
                  size: 48,
                  color: AppColors.textSecondary.withValues(alpha: 0.5),
                ),
                const SizedBox(height: AppSpacing.sm),
                Text(
                  'No notes yet',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
                const SizedBox(height: AppSpacing.xs),
                Text(
                  'Tap + to add your first note',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: AppColors.textSecondary,
                  ),
                ),
              ],
            ),
          )
        else
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: _notes.length,
            separatorBuilder: (context, index) =>
                const SizedBox(height: AppSpacing.md),
            itemBuilder: (context, index) => _buildNoteCard(_notes[index]),
          ),
      ],
    );
  }

  Widget _buildItemIdSection(BuildContext context) {
    final theme = Theme.of(context);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Item ID', style: theme.textTheme.titleMedium),
        const SizedBox(height: AppSpacing.sm),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(AppSpacing.md),
          decoration: BoxDecoration(
            color: AppColors.badgeBackground,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            children: [
              Expanded(
                child: SelectableText(
                  widget.item.id,
                  style: theme.textTheme.bodySmall?.copyWith(
                    fontFamily: 'monospace',
                    color: AppColors.textSecondary,
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.copy, size: 16),
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: widget.item.id));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Item ID copied')),
                  );
                },
                tooltip: 'Copy ID',
                visualDensity: VisualDensity.compact,
                color: AppColors.textSecondary,
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildNoteCard(ItemNote note) {
    final theme = Theme.of(context);
    final dateStr = DateFormat.yMMMd().add_jm().format(note.createdAt);

    return Card(
      elevation: 0,
      color: AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(8),
        side: const BorderSide(color: AppColors.divider),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Image if present
          if (note.imagePath != null && note.imagePath!.isNotEmpty)
            ClipRRect(
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(8)),
              child: CachedNetworkImage(
                imageUrl: note.imagePath!,
                httpHeaders: widget.authToken != null
                    ? {'Authorization': 'Bearer ${widget.authToken}'}
                    : null,
                height: 150,
                width: double.infinity,
                fit: BoxFit.cover,
                placeholder: (context, url) => Container(
                  height: 150,
                  color: AppColors.badgeBackground,
                  child: const Center(
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                ),
                errorWidget: (context, url, error) => Container(
                  height: 150,
                  color: AppColors.badgeBackground,
                  child: const Center(
                    child: Icon(Icons.broken_image_outlined),
                  ),
                ),
              ),
            ),

          Padding(
            padding: const EdgeInsets.all(AppSpacing.md),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Follow-up badge
                if (note.noteType == 'follow_up')
                  Container(
                    margin: const EdgeInsets.only(bottom: 4),
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: Colors.orange.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      'Follow-up',
                      style: TextStyle(
                        fontSize: 11,
                        color: Colors.orange[800],
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ),
                // Note text
                if (note.text != null && note.text!.isNotEmpty)
                  Text(
                    note.text!,
                    style: theme.textTheme.bodyMedium,
                  ),

                const SizedBox(height: AppSpacing.sm),

                // Timestamp and actions
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      dateStr,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: AppColors.textSecondary,
                      ),
                    ),
                    Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        IconButton(
                          icon: const Icon(Icons.edit_outlined, size: 18),
                          onPressed: () => _editNote(note),
                          tooltip: 'Edit note',
                          visualDensity: VisualDensity.compact,
                          color: AppColors.textSecondary,
                        ),
                        IconButton(
                          icon: const Icon(Icons.delete_outline, size: 18),
                          onPressed: () => _deleteNote(note),
                          tooltip: 'Delete note',
                          visualDensity: VisualDensity.compact,
                          color: AppColors.error,
                        ),
                      ],
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _launchUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  void _copyToClipboard(BuildContext context, String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Copied to clipboard')),
    );
  }

  String _formatFileSize(int bytes) {
    if (bytes < 1024) return '$bytes B';
    if (bytes < 1024 * 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    if (bytes < 1024 * 1024 * 1024) {
      return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }

  String _formatDuration(int seconds) {
    final mins = seconds ~/ 60;
    final secs = seconds % 60;
    return '$mins:${secs.toString().padLeft(2, '0')}';
  }
}

/// Bottom sheet widget for adding notes
class _AddNoteBottomSheet extends StatefulWidget {
  final ImagePicker imagePicker;

  const _AddNoteBottomSheet({required this.imagePicker});

  @override
  State<_AddNoteBottomSheet> createState() => _AddNoteBottomSheetState();
}

class _AddNoteBottomSheetState extends State<_AddNoteBottomSheet> {
  final TextEditingController _textController = TextEditingController();
  String? _selectedImagePath;
  bool _isFollowUp = false;

  @override
  void dispose() {
    _textController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(
        bottom: MediaQuery.of(context).viewInsets.bottom,
        left: AppSpacing.lg,
        right: AppSpacing.lg,
        top: AppSpacing.lg,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'Add Note',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              IconButton(
                icon: const Icon(Icons.close),
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.md),
          TextField(
            controller: _textController,
            maxLines: 4,
            decoration: const InputDecoration(
              hintText: 'Write your note...',
              border: OutlineInputBorder(),
            ),
          ),
          const SizedBox(height: AppSpacing.md),
          CheckboxListTile(
            value: _isFollowUp,
            onChanged: (v) => setState(() => _isFollowUp = v ?? false),
            title: const Text('Follow-up response'),
            controlAffinity: ListTileControlAffinity.leading,
            contentPadding: EdgeInsets.zero,
            dense: true,
          ),
          if (_selectedImagePath != null) ...[
            Stack(
              children: [
                Container(
                  height: 100,
                  width: double.infinity,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(8),
                    color: AppColors.badgeBackground,
                  ),
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.file(
                      File(_selectedImagePath!),
                      fit: BoxFit.cover,
                      errorBuilder: (context, error, stackTrace) => const Center(
                        child: Icon(Icons.image, size: 40),
                      ),
                    ),
                  ),
                ),
                Positioned(
                  top: 4,
                  right: 4,
                  child: Container(
                    decoration: BoxDecoration(
                      color: Colors.black54,
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: IconButton(
                      icon: const Icon(Icons.close, color: Colors.white, size: 18),
                      onPressed: () {
                        setState(() {
                          _selectedImagePath = null;
                        });
                      },
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.md),
          ],
          Row(
            children: [
              IconButton(
                icon: const Icon(Icons.photo_library),
                onPressed: () async {
                  final image = await widget.imagePicker.pickImage(
                    source: ImageSource.gallery,
                  );
                  if (image != null) {
                    setState(() {
                      _selectedImagePath = image.path;
                    });
                  }
                },
                tooltip: 'Pick from gallery',
              ),
              IconButton(
                icon: const Icon(Icons.camera_alt),
                onPressed: () async {
                  final image = await widget.imagePicker.pickImage(
                    source: ImageSource.camera,
                  );
                  if (image != null) {
                    setState(() {
                      _selectedImagePath = image.path;
                    });
                  }
                },
                tooltip: 'Take photo',
              ),
              const Spacer(),
              ElevatedButton(
                onPressed: () {
                  final text = _textController.text.trim();
                  if (text.isEmpty && _selectedImagePath == null) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('Please add text or an image')),
                    );
                    return;
                  }

                  Navigator.of(context).pop({
                    'text': text.isNotEmpty ? text : null,
                    'imagePath': _selectedImagePath,
                    'noteType': _isFollowUp ? 'follow_up' : 'context',
                  });
                },
                child: const Text('Save'),
              ),
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
        ],
      ),
    );
  }
}
