import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';

class TypeBadge extends StatelessWidget {
  final String type;

  const TypeBadge({super.key, required this.type});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.sm,
        vertical: AppSpacing.xs,
      ),
      decoration: BoxDecoration(
        color: AppColors.badgeBackground,
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            _getIcon(),
            size: 14,
            color: AppColors.badgeText,
          ),
          const SizedBox(width: AppSpacing.xs),
          Text(
            _getLabel(),
            style: Theme.of(context).textTheme.labelMedium,
          ),
        ],
      ),
    );
  }

  IconData _getIcon() {
    switch (type) {
      case 'image':
        return Icons.image_outlined;
      case 'video':
        return Icons.videocam_outlined;
      case 'web_url':
        return Icons.link;
      case 'file':
        return Icons.insert_drive_file_outlined;
      case 'audio':
        return Icons.audiotrack_outlined;
      case 'screenshot':
        return Icons.screenshot_outlined;
      default:
        return Icons.text_fields;
    }
  }

  String _getLabel() {
    switch (type) {
      case 'web_url':
        return 'Link';
      case 'image':
        return 'Image';
      case 'video':
        return 'Video';
      case 'file':
        return 'File';
      case 'audio':
        return 'Audio';
      case 'screenshot':
        return 'Screenshot';
      default:
        return 'Text';
    }
  }
}
