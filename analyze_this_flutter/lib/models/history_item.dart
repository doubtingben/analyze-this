class ShareItemMetadata {
  final String? fileName;
  final String? mimeType;
  final int? fileSize;
  final int? duration;
  final int? width;
  final int? height;

  ShareItemMetadata({
    this.fileName,
    this.mimeType,
    this.fileSize,
    this.duration,
    this.width,
    this.height,
  });

  factory ShareItemMetadata.fromJson(Map<String, dynamic> json) {
    return ShareItemMetadata(
      fileName: json['fileName'] ?? json['file_name'],
      mimeType: json['mimeType'] ?? json['mime_type'],
      fileSize: json['fileSize'] ?? json['file_size'],
      duration: json['duration'],
      width: json['width'],
      height: json['height'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'fileName': fileName,
      'mimeType': mimeType,
      'fileSize': fileSize,
      'duration': duration,
      'width': width,
      'height': height,
    };
  }
}

class HistoryItem {
  final String id;
  final int timestamp;
  final String value;
  final String type;
  final String? firestoreId;
  final String? title;
  final ShareItemMetadata? metadata;
  final Map<String, dynamic>? analysis;
  final String? status;
  final String? nextStep;

  HistoryItem({
    required this.id,
    required this.timestamp,
    required this.value,
    this.type = 'text',
    this.firestoreId,
    this.title,
    this.metadata,
    this.analysis,
    this.status,
    this.nextStep,
  });

  factory HistoryItem.fromJson(Map<String, dynamic> json) {
    // Normalization logic similar to normalizeShareType in useShareHistory.ts
    // can be added here or in the service. For now, we map direct fields.
    final rawValue = json['content'] ?? json['value'] ?? '';
    
    return HistoryItem(
      id: json['firestore_id'] ?? json['id'] ?? '',
      timestamp: json['created_at'] != null 
          ? DateTime.parse(json['created_at']).millisecondsSinceEpoch 
          : (json['timestamp'] ?? DateTime.now().millisecondsSinceEpoch),
      value: rawValue,
      type: _normalizeType(json['type'], rawValue, json['item_metadata']),
      firestoreId: json['firestore_id'],
      title: json['title'],
      metadata: json['item_metadata'] != null 
          ? ShareItemMetadata.fromJson(Map<String, dynamic>.from(json['item_metadata'])) 
          : null,
      analysis: json['analysis'] != null ? Map<String, dynamic>.from(json['analysis']) : null,
      status: json['status'],
      nextStep: json['next_step'] ?? json['next_step_label'], // Handling potential field name variance
    );
  }

  static String _normalizeType(String? rawType, String value, Map<String, dynamic>? metadata) {
    String normalized = (rawType ?? '').toLowerCase();
    
    if (normalized == 'weburl' || normalized == 'web_url') return 'web_url';
    
    // Check metadata mimeType if available
    final mimeType = metadata?['mimeType'] ?? metadata?['mime_type'];
    if (mimeType != null && mimeType is String) {
      if (mimeType.startsWith('image/')) return 'image';
      if (mimeType.startsWith('video/')) return 'video';
      if (mimeType.startsWith('audio/')) return 'audio';
    }

    if (normalized == 'file') return 'file';
    
    if (['image', 'video', 'audio', 'screenshot', 'text'].contains(normalized)) {
      return normalized;
    }

    // Inference from value extension
    final lowerValue = value.toLowerCase();
    if (RegExp(r'\.(png|jpe?g|gif|webp|bmp|tiff|svg)$').hasMatch(lowerValue)) return 'image';
    if (RegExp(r'\.(mp4|mov|m4v|webm|avi|mkv)$').hasMatch(lowerValue)) return 'video';
    if (RegExp(r'\.(mp3|wav|m4a|aac|flac|ogg)$').hasMatch(lowerValue)) return 'audio';

    if (normalized == 'media') return 'image';

    return 'text';
  }
}
