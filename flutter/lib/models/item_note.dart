class ItemNote {
  final String id;
  final String itemId;
  final String userEmail;
  final String? text;
  final String? imagePath;
  final String noteType;
  final DateTime createdAt;
  final DateTime updatedAt;

  ItemNote({
    required this.id,
    required this.itemId,
    required this.userEmail,
    this.text,
    this.imagePath,
    this.noteType = 'context',
    required this.createdAt,
    required this.updatedAt,
  });

  factory ItemNote.fromJson(Map<String, dynamic> json) {
    return ItemNote(
      id: json['id'] ?? '',
      itemId: json['item_id'] ?? '',
      userEmail: json['user_email'] ?? '',
      text: json['text'],
      imagePath: json['image_path'],
      noteType: json['note_type'] ?? 'context',
      createdAt: json['created_at'] != null
          ? DateTime.parse(json['created_at'])
          : DateTime.now(),
      updatedAt: json['updated_at'] != null
          ? DateTime.parse(json['updated_at'])
          : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'item_id': itemId,
      'user_email': userEmail,
      'text': text,
      'image_path': imagePath,
      'note_type': noteType,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  ItemNote copyWith({
    String? id,
    String? itemId,
    String? userEmail,
    String? text,
    String? imagePath,
    String? noteType,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return ItemNote(
      id: id ?? this.id,
      itemId: itemId ?? this.itemId,
      userEmail: userEmail ?? this.userEmail,
      text: text ?? this.text,
      imagePath: imagePath ?? this.imagePath,
      noteType: noteType ?? this.noteType,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}
