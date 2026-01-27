import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../models/history_item.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';
import '../widgets/type_badge.dart';

class ItemDetailScreen extends StatefulWidget {
  final List<HistoryItem> items;
  final int initialIndex;
  final String? authToken;

  const ItemDetailScreen({
    super.key,
    required this.items,
    required this.initialIndex,
    this.authToken,
  });

  @override
  State<ItemDetailScreen> createState() => _ItemDetailScreenState();
}

class _ItemDetailScreenState extends State<ItemDetailScreen> {
  late PageController _pageController;
  late int _currentIndex;

  @override
  void initState() {
    super.initState();
    _currentIndex = widget.initialIndex;
    _pageController = PageController(initialPage: widget.initialIndex);
  }

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  HistoryItem get _currentItem => widget.items[_currentIndex];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_currentItem.title ?? 'Item Details'),
        actions: [
          // Page indicator
          Center(
            child: Padding(
              padding: const EdgeInsets.only(right: AppSpacing.lg),
              child: Text(
                '${_currentIndex + 1} / ${widget.items.length}',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ),
          ),
        ],
      ),
      body: PageView.builder(
        controller: _pageController,
        itemCount: widget.items.length,
        onPageChanged: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        itemBuilder: (context, index) {
          return _ItemDetailPage(
            item: widget.items[index],
            authToken: widget.authToken,
          );
        },
      ),
    );
  }
}

class _ItemDetailPage extends StatelessWidget {
  final HistoryItem item;
  final String? authToken;

  const _ItemDetailPage({
    required this.item,
    this.authToken,
  });

  bool get _hasAnalysis => item.analysis != null && item.analysis!.isNotEmpty;
  bool get _isImageType => item.type == 'image' || item.type == 'screenshot';
  bool get _isUrlType => item.type == 'web_url';

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final dateStr = DateFormat.yMMMd().add_jm().format(
      DateTime.fromMillisecondsSinceEpoch(item.timestamp),
    );

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Media preview
          if (_isImageType && item.value.isNotEmpty)
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
                    TypeBadge(type: item.type),
                    const SizedBox(width: AppSpacing.md),
                    Text(dateStr, style: theme.textTheme.bodySmall),
                  ],
                ),
                const SizedBox(height: AppSpacing.lg),

                // Title
                if (item.title != null) ...[
                  Text(
                    item.title!,
                    style: theme.textTheme.titleLarge,
                  ),
                  const SizedBox(height: AppSpacing.md),
                ],

                // Content/Value
                _buildContentSection(context),

                // Metadata section
                if (item.metadata != null) ...[
                  const SizedBox(height: AppSpacing.xl),
                  _buildMetadataSection(context),
                ],

                // Analysis section
                if (_hasAnalysis) ...[
                  const SizedBox(height: AppSpacing.xl),
                  _buildAnalysisSection(context),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildImagePreview() {
    return AspectRatio(
      aspectRatio: 4 / 3,
      child: CachedNetworkImage(
        imageUrl: item.value,
        httpHeaders: authToken != null
            ? {'Authorization': 'Bearer $authToken'}
            : null,
        fit: BoxFit.contain,
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
              size: 48,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildContentSection(BuildContext context) {
    final theme = Theme.of(context);

    if (_isUrlType) {
      return InkWell(
        onTap: () => _launchUrl(item.value),
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
                  item.value,
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
            item.value,
            style: theme.textTheme.bodyMedium,
          ),
        ),
        const SizedBox(height: AppSpacing.sm),
        Align(
          alignment: Alignment.centerRight,
          child: TextButton.icon(
            onPressed: () => _copyToClipboard(context, item.value),
            icon: const Icon(Icons.copy, size: 16),
            label: const Text('Copy'),
          ),
        ),
      ],
    );
  }

  Widget _buildMetadataSection(BuildContext context) {
    final theme = Theme.of(context);
    final meta = item.metadata!;
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
      entries.add(MapEntry('Dimensions', '${meta.width} × ${meta.height}'));
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
            children: entries.map((e) => Padding(
              padding: const EdgeInsets.symmetric(vertical: AppSpacing.xs),
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
            )).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildAnalysisSection(BuildContext context) {
    final theme = Theme.of(context);
    final analysis = item.analysis!;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('Analysis', style: theme.textTheme.titleMedium),
            const SizedBox(width: AppSpacing.sm),
            const Text('✨', style: TextStyle(fontSize: 18)),
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

        // Tags
        if (analysis['tags'] != null && (analysis['tags'] as List).isNotEmpty) ...[
          Text('Tags', style: theme.textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w500)),
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.sm,
            children: (analysis['tags'] as List).map((tag) => Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.sm,
                vertical: AppSpacing.xs,
              ),
              decoration: BoxDecoration(
                color: AppColors.badgeBackground,
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                tag.toString(),
                style: theme.textTheme.labelMedium,
              ),
            )).toList(),
          ),
        ],
      ],
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
    if (bytes < 1024 * 1024 * 1024) return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    return '${(bytes / (1024 * 1024 * 1024)).toStringAsFixed(1)} GB';
  }

  String _formatDuration(int seconds) {
    final mins = seconds ~/ 60;
    final secs = seconds % 60;
    return '${mins}:${secs.toString().padLeft(2, '0')}';
  }
}
