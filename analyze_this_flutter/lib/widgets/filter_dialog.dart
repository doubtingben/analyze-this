import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';

/// A bottom sheet dialog for filtering items by type and tag.
class FilterDialog extends StatefulWidget {
  final Set<String> selectedTypes;
  final Set<String> selectedTags;
  final Set<String> availableTags;
  final void Function(Set<String> types, Set<String> tags) onApply;

  const FilterDialog({
    super.key,
    required this.selectedTypes,
    required this.selectedTags,
    required this.availableTags,
    required this.onApply,
  });

  @override
  State<FilterDialog> createState() => _FilterDialogState();

  /// Shows the filter dialog as a modal bottom sheet.
  static Future<void> show({
    required BuildContext context,
    required Set<String> selectedTypes,
    required Set<String> selectedTags,
    required Set<String> availableTags,
    required void Function(Set<String> types, Set<String> tags) onApply,
  }) {
    return showModalBottomSheet(
      context: context,
      showDragHandle: true,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) => FilterDialog(
        selectedTypes: selectedTypes,
        selectedTags: selectedTags,
        availableTags: availableTags,
        onApply: onApply,
      ),
    );
  }
}

class _FilterDialogState extends State<FilterDialog> {
  late Set<String> _types;
  late Set<String> _tags;

  // All available types in the app
  static const List<_TypeOption> _allTypes = [
    _TypeOption(value: 'image', label: 'Image', icon: Icons.image_outlined),
    _TypeOption(value: 'video', label: 'Video', icon: Icons.videocam_outlined),
    _TypeOption(value: 'audio', label: 'Audio', icon: Icons.audiotrack_outlined),
    _TypeOption(value: 'file', label: 'File', icon: Icons.insert_drive_file_outlined),
    _TypeOption(value: 'screenshot', label: 'Screenshot', icon: Icons.screenshot_outlined),
    _TypeOption(value: 'text', label: 'Text', icon: Icons.text_fields),
    _TypeOption(value: 'web_url', label: 'Link', icon: Icons.link),
  ];

  @override
  void initState() {
    super.initState();
    _types = Set.from(widget.selectedTypes);
    _tags = Set.from(widget.selectedTags);
  }

  void _clearAll() {
    setState(() {
      _types.clear();
      _tags.clear();
    });
  }

  void _apply() {
    widget.onApply(_types, _tags);
    Navigator.of(context).pop();
  }

  bool get _hasFilters => _types.isNotEmpty || _tags.isNotEmpty;

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.lg,
          0,
          AppSpacing.lg,
          AppSpacing.lg,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Filter',
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                if (_hasFilters)
                  TextButton(
                    onPressed: _clearAll,
                    child: const Text('Clear all'),
                  ),
              ],
            ),
            const SizedBox(height: AppSpacing.lg),

            // Types section
            Text(
              'Types',
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
            const SizedBox(height: AppSpacing.sm),
            Wrap(
              spacing: AppSpacing.sm,
              runSpacing: AppSpacing.sm,
              children: _allTypes.map((type) {
                final isSelected = _types.contains(type.value);
                return FilterChip(
                  label: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        type.icon,
                        size: 16,
                        color: isSelected ? AppColors.primary : AppColors.textSecondary,
                      ),
                      const SizedBox(width: AppSpacing.xs),
                      Text(type.label),
                    ],
                  ),
                  selected: isSelected,
                  onSelected: (selected) {
                    setState(() {
                      if (selected) {
                        _types.add(type.value);
                      } else {
                        _types.remove(type.value);
                      }
                    });
                  },
                );
              }).toList(),
            ),
            const SizedBox(height: AppSpacing.xl),

            // Tags section
            if (widget.availableTags.isNotEmpty) ...[
              Text(
                'Tags',
                style: Theme.of(context).textTheme.titleSmall?.copyWith(
                  color: AppColors.textSecondary,
                ),
              ),
              const SizedBox(height: AppSpacing.sm),
              Wrap(
                spacing: AppSpacing.sm,
                runSpacing: AppSpacing.sm,
                children: widget.availableTags.map((tag) {
                  final isSelected = _tags.contains(tag);
                  return FilterChip(
                    label: Text(tag),
                    selected: isSelected,
                    onSelected: (selected) {
                      setState(() {
                        if (selected) {
                          _tags.add(tag);
                        } else {
                          _tags.remove(tag);
                        }
                      });
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: AppSpacing.xl),
            ],

            // Action buttons
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    child: const Text('Cancel'),
                  ),
                ),
                const SizedBox(width: AppSpacing.md),
                Expanded(
                  child: FilledButton(
                    onPressed: _apply,
                    child: const Text('Apply'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Helper class for type options.
class _TypeOption {
  final String value;
  final String label;
  final IconData icon;

  const _TypeOption({
    required this.value,
    required this.label,
    required this.icon,
  });
}
