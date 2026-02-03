import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:mime/mime.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';
import '../config.dart';
import '../models/history_item.dart';
import '../models/item_note.dart';

class ApiService {
  Future<List<HistoryItem>> fetchHistory(String token) async {
    final response = await http.get(
      Uri.parse('${Config.apiUrl}/api/items'),
      headers: {
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => HistoryItem.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load history: ${response.statusCode}');
    }
  }

  Future<void> deleteItem(String token, String id) async {
    final response = await http.delete(
      Uri.parse('${Config.apiUrl}/api/items/$id'),
      headers: {
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode != 200 && response.statusCode != 204) {
      throw Exception('Failed to delete item: ${response.statusCode}');
    }
  }

  Future<void> setItemHidden(String token, String id, bool hidden) async {
    final action = hidden ? 'hide' : 'unhide';
    final response = await http.patch(
      Uri.parse('${Config.apiUrl}/api/items/$id/$action'),
      headers: {
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode != 200 && response.statusCode != 204) {
      throw Exception('Failed to update item visibility: ${response.statusCode}');
    }
  }

  Future<Uint8List> exportData(String token) async {
    final response = await http.get(
      Uri.parse('${Config.apiUrl}/api/export'),
      headers: {
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      return response.bodyBytes;
    }
    throw Exception('Failed to export data: ${response.statusCode}');
  }

  Future<void> uploadShare(
    String token,
    ShareItemType type,
    String value,
    String userEmail, {
    List<SharedMediaFile>? files,
    String? fileName,
    int? fileSize,
    int? width,
    int? height,
    double? duration,
  }) async {
    final uri = Uri.parse('${Config.apiUrl}/api/share');
    final request = http.MultipartRequest('POST', uri);
    
    request.headers['Authorization'] = 'Bearer $token';
    
    // Add text fields
    request.fields['type'] = _mapShareTypeToString(type);
    request.fields['content'] = value;
    request.fields['user_email'] = userEmail;
    request.fields['title'] = _generateFallbackTitle(type, value, fileName: fileName);

    // Handle File Upload
    if (files != null && files.isNotEmpty) {
      final file = files.first;
      final mimeTypeStr = file.mimeType ?? lookupMimeType(file.path) ?? 'application/octet-stream';
      final mediaType = MediaType.parse(mimeTypeStr);

      request.files.add(await http.MultipartFile.fromPath(
        'file',
        file.path,
        contentType: mediaType,
        filename: file.path.split('/').last,
      ));
      
      // Add standard metadata fields expected by backend
      request.fields['mime_type'] = mimeTypeStr;
      
      if (fileName != null) request.fields['file_name'] = fileName;
      if (fileSize != null) request.fields['file_size'] = fileSize.toString();
      if (width != null) request.fields['width'] = width.toString();
      if (height != null) request.fields['height'] = height.toString();
      if (duration != null) request.fields['duration'] = duration.toString();
    } else {
      // If no file, ensure we treat it as JSON/Text request if preferred, 
      // but MultipartRequest works for fields too.
      // The backend (Python/FastAPI usually) handles form data.
      // For pure JSON requests (links/text), use JSON unless files are present.
    }
    
    // Switch to JSON request if no actual file to ensure backend compatibility
    // Use FormData when files exist, JSON otherwise.
    if (files == null || files.isEmpty) {
      final jsonResponse = await http.post(
        uri,
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'title': _generateFallbackTitle(type, value, fileName: fileName),
          'content': value,
          'type': _mapShareTypeToString(type),
          'user_email': userEmail,
        }),
      );
       if (jsonResponse.statusCode != 200 && jsonResponse.statusCode != 201) {
          throw Exception('Failed to share item: ${jsonResponse.statusCode} ${jsonResponse.body}');
       }
       return;
    }

    final response = await request.send();
    if (response.statusCode != 200 && response.statusCode != 201) {
      final respStr = await response.stream.bytesToString();
      throw Exception('Failed to share item: ${response.statusCode} $respStr');
    }
  }

  /// Update item (title, tags, status, next_step, follow_up)
  Future<void> updateItem(
    String token,
    String itemId, {
    String? title,
    List<String>? tags,
    String? status,
    String? nextStep,
    String? followUp,
  }) async {
    final body = <String, dynamic>{};
    if (title != null) body['title'] = title;
    if (tags != null) body['tags'] = tags;
    if (status != null) body['status'] = status;
    if (nextStep != null) body['next_step'] = nextStep;
    if (followUp != null) body['follow_up'] = followUp;

    if (body.isEmpty) {
      throw ArgumentError('At least one field must be provided');
    }

    final response = await http.patch(
      Uri.parse('${Config.apiUrl}/api/items/$itemId'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: jsonEncode(body),
    );

    if (response.statusCode != 200 && response.statusCode != 204) {
      throw Exception('Failed to update item: ${response.statusCode}');
    }
  }

  /// Get all notes for an item
  Future<List<ItemNote>> getItemNotes(String token, String itemId) async {
    final response = await http.get(
      Uri.parse('${Config.apiUrl}/api/items/$itemId/notes'),
      headers: {
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      final List<dynamic> data = jsonDecode(response.body);
      return data.map((json) => ItemNote.fromJson(json)).toList();
    } else {
      throw Exception('Failed to load notes: ${response.statusCode}');
    }
  }

  /// Create a note for an item (with optional file attachment)
  Future<ItemNote> createNote(String token, String itemId, {String? text, String? imagePath}) async {
    if (text == null && imagePath == null) {
      throw ArgumentError('At least one of text or imagePath must be provided');
    }

    final uri = Uri.parse('${Config.apiUrl}/api/items/$itemId/notes');

    if (imagePath != null) {
      // Multipart request for file upload
      final request = http.MultipartRequest('POST', uri);
      request.headers['Authorization'] = 'Bearer $token';

      if (text != null) {
        request.fields['text'] = text;
      }

      final mimeTypeStr = lookupMimeType(imagePath) ?? 'application/octet-stream';
      final mediaType = MediaType.parse(mimeTypeStr);

      request.files.add(await http.MultipartFile.fromPath(
        'file',
        imagePath,
        contentType: mediaType,
        filename: imagePath.split('/').last,
      ));

      final response = await request.send();
      final respBody = await response.stream.bytesToString();
      if (response.statusCode != 200 && response.statusCode != 201) {
        throw Exception('Failed to create note: ${response.statusCode} $respBody');
      }
      return ItemNote.fromJson(jsonDecode(respBody));
    } else {
      // Simple POST with form data for text-only note
      final request = http.MultipartRequest('POST', uri);
      request.headers['Authorization'] = 'Bearer $token';
      request.fields['text'] = text!;

      final response = await request.send();
      final respBody = await response.stream.bytesToString();
      if (response.statusCode != 200 && response.statusCode != 201) {
        throw Exception('Failed to create note: ${response.statusCode} $respBody');
      }
      return ItemNote.fromJson(jsonDecode(respBody));
    }
  }

  /// Update a note's text (imagePath updates not yet supported by backend)
  Future<void> updateNote(String token, String noteId, {String? text, String? imagePath}) async {
    if (text == null && imagePath == null) {
      throw ArgumentError('At least one of text or imagePath must be provided');
    }

    // Note: Backend currently only supports text updates
    // imagePath parameter is reserved for future use
    final body = <String, dynamic>{};
    if (text != null) body['text'] = text;

    final response = await http.patch(
      Uri.parse('${Config.apiUrl}/api/notes/$noteId'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: jsonEncode(body),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to update note: ${response.statusCode}');
    }
  }

  /// Delete a note
  Future<void> deleteNote(String token, String noteId) async {
    final response = await http.delete(
      Uri.parse('${Config.apiUrl}/api/notes/$noteId'),
      headers: {
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode != 200 && response.statusCode != 204) {
      throw Exception('Failed to delete note: ${response.statusCode}');
    }
  }

  /// Get note counts for multiple items
  Future<Map<String, int>> getNoteCounts(String token, List<String> itemIds) async {
    if (itemIds.isEmpty) {
      return {};
    }

    final response = await http.post(
      Uri.parse('${Config.apiUrl}/api/items/note-counts'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({'item_ids': itemIds}),
    );

    if (response.statusCode == 200) {
      final Map<String, dynamic> data = jsonDecode(response.body);
      return data.map((key, value) => MapEntry(key, value as int));
    } else {
      throw Exception('Failed to get note counts: ${response.statusCode}');
    }
  }

  /// Get user metrics (item counts by status)
  Future<Map<String, dynamic>> getMetrics(String token) async {
    final response = await http.get(
      Uri.parse('${Config.apiUrl}/api/metrics'),
      headers: {
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } else {
      throw Exception('Failed to load metrics: ${response.statusCode}');
    }
  }

  /// Get user profile
  Future<Map<String, dynamic>> getUserProfile(String token) async {
    final response = await http.get(
      Uri.parse('${Config.apiUrl}/api/user'),
      headers: {
        'Authorization': 'Bearer $token',
      },
    );

    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    } else {
      throw Exception('Failed to load user profile: ${response.statusCode}');
    }
  }

  // Helpers
  String _mapShareTypeToString(ShareItemType type) {
    if (type == ShareItemType.text) return 'text';
    if (type == ShareItemType.webUrl) return 'web_url';
    if (type == ShareItemType.image) return 'image';
    if (type == ShareItemType.video) return 'video';
    if (type == ShareItemType.file) return 'file';
    return 'text';
  }
  
  String _generateFallbackTitle(ShareItemType type, String value, {String? fileName}) {
      switch (type) {
        case ShareItemType.webUrl:
            try {
                final uri = Uri.parse(value);
                return uri.host.replaceFirst('www.', '');
            } catch (_) {
                return 'Shared Link';
            }
        case ShareItemType.text:
            final preview = value.trim().length > 40 ? '${value.trim().substring(0, 40)}...' : value.trim();
            return preview.isEmpty ? 'Shared Text' : preview;
        case ShareItemType.image:
            if ((fileName != null && fileName.toLowerCase().contains('screenshot')) || 
                value.toLowerCase().contains('screenshot')) {
                return 'Shared Screenshot';
            }
            return 'Shared Image';
        case ShareItemType.video:
            return 'Shared Video';
        default:
            return 'Shared Item';
    }
  }
}

// Enum mapping to match the usage in main.dart/ShareMediaFile
enum ShareItemType {
  text,
  webUrl,
  image,
  video,
  file,
}
