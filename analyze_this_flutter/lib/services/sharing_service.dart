import 'dart:async';
import 'dart:convert';
import 'package:app_links/app_links.dart';
import 'package:flutter/services.dart';

class SharingService {
  static const MethodChannel _channel = MethodChannel('com.analyzethis/share');
  static final SharingService _instance = SharingService._internal();

  factory SharingService() => _instance;

  SharingService._internal();

  final _appLinks = AppLinks();
  StreamSubscription? _linkSubscription;

  // Stream controller to broadcast received shared items to the app
  final _sharedContentController = StreamController<List<SharedItem>>.broadcast();
  Stream<List<SharedItem>> get sharedContentStream => _sharedContentController.stream;

  void initialize() {
    _initDeepLinks();
    _checkInitialShare();
  }

  void _initDeepLinks() {
    _linkSubscription = _appLinks.uriLinkStream.listen((uri) {
      if (uri.scheme == 'analyzethis') {
        _handleShareDeepLink(uri);
      }
    });
  }

  Future<void> _checkInitialShare() async {
      // Check if app was launched via deep link
      try {
        final uri = await _appLinks.getInitialAppLink();
        if (uri != null && uri.scheme == 'analyzethis') {
             _handleShareDeepLink(uri);
        }
      } catch (e) {
          // Ignore
      }
  }

  Future<void> _handleShareDeepLink(Uri uri) async {
    try {
      final dynamic data = await _channel.invokeMethod('getSharedData');
      if (data != null) {
        
        List<SharedItem> items = [];
        
        if (data is String) {
             // Could be raw text or JSON depending on what Swift sent. 
             // Swift code sends:
             // - Text: [String]
             // - WebURL: JSON of [WebUrl]
             // - Media: JSON of [SharedMediaFile]
             
             // However, method channel result from Swift 'result(data)' where data is read from UserDefaults.
             // Swift 'userDefaults?.object(forKey: key)'.
             // If Swift set([String], forKey), it comes back as List<Object?> in Flutter?
             // If Swift set(Data, forKey), it comes back as Uint8List/List<int>?
             
             // Let's look at Swift:
             // Text: userDefaults?.set([String], forKey) -> List
             // WebURL: userDefaults?.set(Data, forKey) -> Uint8List (JSON)
             // Media: userDefaults?.set(Data, forKey) -> Uint8List (JSON)
             
             // Wait, if it's List (from Text), it might come as List.
        }

        // We need to handle different types.
        // But wait, the Swift code behaves differently for Text vs others.
        // Text is saved as [String] directly.
        // WebUrl/Media is saved as Data (JSON encoded).
        
        // So 'data' type will vary.
        if (data is Uint8List) {
             final jsonString = utf8.decode(data);
             final jsonData = jsonDecode(jsonString);
             
             // Check for new structure (CombinedData) first
             if (jsonData is Map<String, dynamic> && (jsonData.containsKey('media') || jsonData.containsKey('text') || jsonData.containsKey('webUrls'))) {
                  
                  // Priority 1: Media
                  if (jsonData['media'] != null) {
                      final mediaList = jsonData['media'] as List;
                      items.addAll(mediaList.map((e) => SharedItem.fromJson(e)));
                  }
                  
                  // Priority 2: WebUrls (only if no media? or append? User prefers Image data)
                  // If we have media, maybe we skip parsing URLs if they are just the page?
                  // Let's add them all and let main.dart filter/prioritize, OR filter here.
                  // Since passing mixed types to main might be confusing if not handled, let's just add everything.
                  if (jsonData['webUrls'] != null) {
                      final urlList = jsonData['webUrls'] as List;
                      items.addAll(urlList.map((e) => SharedItem.fromJson(e)));
                  }
                  
                  // Priority 3: Text
                  if (jsonData['text'] != null) {
                      final textList = jsonData['text'] as List;
                      items.addAll(textList.map((e) => SharedItem(type: SharedMediaType.text, value: e.toString())));
                  }
                  
             } else if (jsonData is List) {
                  // Fallback for legacy array format (shouldn't happen with new Swift code but good for safety)
                  items = jsonData.map((e) => SharedItem.fromJson(e)).toList();
             }
        } else if (data is List) {
             // Fallback for legacy [String] text
             items = data.map((e) => SharedItem(type: SharedMediaType.text, value: e.toString())).toList();
        }

        if (items.isNotEmpty) {
           _sharedContentController.add(items);
        }

        // Clear data after reading
        await _channel.invokeMethod('clearSharedData');
      }
    } catch (e) {
      print('Error handling share: $e');
    }
  }

  void dispose() {
    _linkSubscription?.cancel();
    _sharedContentController.close();
  }
}

enum SharedMediaType {
  image,
  video,
  file,
  weburl, // Mapped from Swift 'weburl' type
  text,   // Mapped from Swift 'text' type logic
}

class SharedItem {
  final SharedMediaType type;
  final String value; // URL or Text
  final String? thumbnail;
  final String? fileName;
  final int? fileSize;
  final int? width;
  final int? height;
  final double? duration;
  final String? mimeType;
  final String? meta; // for web meta

  SharedItem({
    required this.type,
    required this.value,
    this.thumbnail,
    this.fileName,
    this.fileSize,
    this.width,
    this.height,
    this.duration,
    this.mimeType,
    this.meta,
  });

  factory SharedItem.fromJson(Map<String, dynamic> json) {
    // Determine type from JSON structure or 'type' field
    // Swift SharedMediaFile has 'type' (int enum) and 'path'
    // Swift WebUrl has 'url' and 'meta'
    
    if (json.containsKey('url')) {
        return SharedItem(
            type: SharedMediaType.weburl,
            value: json['url'],
            meta: json['meta'],
        );
    } else {
        // SharedMediaFile
        // type enum: 0=image, 1=video, 2=file
        final typeInt = json['type'] as int?;
        SharedMediaType type = SharedMediaType.file;
        if (typeInt == 0) type = SharedMediaType.image;
        else if (typeInt == 1) type = SharedMediaType.video;
        else if (typeInt == 2) type = SharedMediaType.file;
        
        String path = json['path'];
        if (path.startsWith('file://')) {
          try {
            path = Uri.parse(path).toFilePath();
          } catch (e) {
            print('Error parsing URI: $e');
            // Fallback: strip file:// manually if toFilePath fails
            path = path.replaceFirst('file://', '');
          }
        }

        return SharedItem(
            type: type,
            value: path,
            thumbnail: json['thumbnail'],
            fileName: json['fileName'],
            fileSize: json['fileSize'],
            width: json['width'],
            height: json['height'],
            duration: json['duration']?.toDouble(),
            mimeType: json['mimeType'],
        );
    }
  }
}
