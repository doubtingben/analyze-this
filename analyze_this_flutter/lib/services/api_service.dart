import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:mime/mime.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';
import '../config.dart';
import '../models/history_item.dart';

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

  Future<void> uploadShare(String token, ShareItemType type, String value, String userEmail, {List<SharedMediaFile>? files}) async {
    final uri = Uri.parse('${Config.apiUrl}/api/share');
    final request = http.MultipartRequest('POST', uri);
    
    request.headers['Authorization'] = 'Bearer $token';
    
    // Add text fields
    request.fields['type'] = _mapShareTypeToString(type);
    request.fields['content'] = value;
    request.fields['user_email'] = userEmail;
    request.fields['title'] = _generateFallbackTitle(type, value);

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
      
      // Note: Other metadata fields (width, height, duration) would require 
      // Platform specific code or additional packages to extract in Flutter.
      // We skip them for now or rely on backend extraction.
    } else {
      // If no file, ensure we treat it as JSON/Text request if preferred, 
      // but MultipartRequest works for fields too.
      // The backend (Python/FastAPI usually) handles form data.
      // However, for pure JSON requests (links/text), the React Native app used JSON unless files were present.
      // Let's stick to Multipart for consistency if it works, or switch based on content.
    }
    
    // Switch to JSON request if no actual file to ensure backend compatibility
    // The React Native app does:
    // if (files) -> FormData
    // else -> JSON
    if (files == null || files.isEmpty) {
      final jsonResponse = await http.post(
        uri,
        headers: {
          'Authorization': 'Bearer $token',
          'Content-Type': 'application/json',
        },
        body: jsonEncode({
          'title': _generateFallbackTitle(type, value),
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

  // Helpers
  String _mapShareTypeToString(ShareItemType type) {
    if (type == ShareItemType.text) return 'text';
    if (type == ShareItemType.web_url) return 'web_url';
    if (type == ShareItemType.image) return 'image';
    if (type == ShareItemType.video) return 'video';
    if (type == ShareItemType.file) return 'file';
    return 'text';
  }
  
  String _generateFallbackTitle(ShareItemType type, String value) {
      switch (type) {
        case ShareItemType.web_url:
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
  web_url,
  image,
  video,
  file,
}
