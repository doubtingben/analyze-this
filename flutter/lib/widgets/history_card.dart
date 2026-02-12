import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../models/history_item.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import 'type_badge.dart';

class HistoryCard extends StatelessWidget {
  final HistoryItem item;
  final VoidCallback? onTap;
  final VoidCallback? onToggleHidden;
  final String? authToken;
  final bool isHidden;
  final bool showImage;
  final bool showDate;
  final bool isHiding;

  const HistoryCard({
    super.key,
    required this.item,
    this.onTap,
    this.onToggleHidden,
    this.authToken,
    this.isHidden = false,
    this.showImage = true,
    this.showDate = true,
    this.isHiding = false,
  });

  bool get _hasAnalysis => item.analysis != null && item.analysis!.isNotEmpty;

  String? get _overview => item.analysis?['overview'] as String?;

  bool get _isImageType => item.type == 'image' || item.type == 'screenshot';

  bool get _hasNotes => item.noteCount > 0;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final dateStr = showDate
        ? DateFormat.yMMMd().add_jm().format(
            DateTime.fromMillisecondsSinceEpoch(item.timestamp),
          )
        : null;

    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            // Image thumbnail (if applicable)
            if (showImage && _isImageType && item.value.isNotEmpty)
              _buildImageThumbnail(),

            // Card content
            Padding(
              padding: const EdgeInsets.all(AppSpacing.lg),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Header row: badge + sparkle + notes + delete button
                  Row(
                    children: [
                      TypeBadge(type: item.type),
                      const SizedBox(width: AppSpacing.sm),
                      _buildSparkle(context),
                      if (_hasNotes) ...[
                        const SizedBox(width: AppSpacing.sm),
                        _buildNoteIndicator(),
                      ],
                      if (isHidden) ...[
                        const SizedBox(width: AppSpacing.sm),
                        _buildHiddenChip(),
                      ],
                      const Spacer(),
                      if (onToggleHidden != null)
                        isHiding
                            ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: AppColors.textSecondary,
                                ),
                              )
                            : IconButton(
                                icon: Icon(
                                  isHidden ? Icons.visibility_off : Icons.visibility,
                                ),
                                iconSize: 20,
                                color: AppColors.textSecondary,
                                padding: EdgeInsets.zero,
                                constraints: const BoxConstraints(),
                                onPressed: onToggleHidden,
                                tooltip: isHidden ? 'Unhide' : 'Hide',
                              ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.md),

                  // Title (with indicator for unnormalized titles)
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (!item.isNormalized)
                        Padding(
                          padding: const EdgeInsets.only(right: 4),
                          child: Text(
                            '•',
                            style: theme.textTheme.titleMedium?.copyWith(
                              color: Colors.grey,
                            ),
                          ),
                        ),
                      Expanded(
                        child: Text(
                          item.title ?? item.value,
                          style: theme.textTheme.titleMedium,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: AppSpacing.sm),

                  // Timestamp
                  if (dateStr != null)
                    Text(
                      dateStr,
                      style: theme.textTheme.bodySmall,
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildImageThumbnail() {
    return ClipRRect(
      borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
      child: SizedBox(
        width: double.infinity,
        height: 180,
        child: CachedNetworkImage(
          imageUrl: item.value,
          httpHeaders: authToken != null
              ? {'Authorization': 'Bearer $authToken'}
              : null,
          fit: BoxFit.cover,
          placeholder: (context, url) => Container(
            color: AppColors.badgeBackground,
            child: Center(
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
                size: 32,
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSparkle(BuildContext context) {
    final sparkle = Text(
      '✨',
      style: const TextStyle(fontSize: 18),
    );

    return GestureDetector(
      onTap: _hasAnalysis
          ? () => _showOverviewDialog(context)
          : null,
      child: Tooltip(
        message: _hasAnalysis ? 'View Analysis' : 'No Analysis',
        child: _hasAnalysis
            ? sparkle
            : ColorFiltered(
                colorFilter: const ColorFilter.matrix(<double>[
                  0.2126, 0.7152, 0.0722, 0, 0,
                  0.2126, 0.7152, 0.0722, 0, 0,
                  0.2126, 0.7152, 0.0722, 0, 0,
                  0,      0,      0,      0.5, 0,
                ]),
                child: sparkle,
              ),
      ),
    );
  }

  Widget _buildHiddenChip() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.badgeBackground,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Text(
        'Hidden',
        style: TextStyle(
          fontSize: 10,
          fontWeight: FontWeight.w600,
          color: AppColors.textSecondary,
        ),
      ),
    );
  }

  Widget _buildNoteIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.primary.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            Icons.note_outlined,
            size: 12,
            color: AppColors.primary,
          ),
          const SizedBox(width: 4),
          Text(
            '${item.noteCount}',
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w600,
              color: AppColors.primary,
            ),
          ),
        ],
      ),
    );
  }

  void _showOverviewDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Analysis'),
        content: SingleChildScrollView(
          child: Text(_overview ?? 'No overview available'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }
}
