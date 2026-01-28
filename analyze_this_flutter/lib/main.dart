import 'dart:async';
import 'package:flutter/material.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:intl/intl.dart';

import 'auth_service.dart';
import 'services/api_service.dart';
import 'models/history_item.dart';
import 'theme/app_theme.dart';
import 'theme/app_colors.dart';
import 'theme/app_spacing.dart';
import 'widgets/history_card.dart';
import 'screens/item_detail_screen.dart';

import 'services/sharing_service.dart' as custom_sharing;

enum ViewMode { all, timeline, followUp }

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Analyze This',
      theme: AppTheme.light,
      home: const MyHomePage(title: 'Analyze This'),
    );
  }
}

class MyHomePage extends StatefulWidget {
  const MyHomePage({super.key, required this.title});

  final String title;

  @override
  State<MyHomePage> createState() => _MyHomePageState();
}

class _MyHomePageState extends State<MyHomePage> {
  StreamSubscription? _intentDataStreamSubscription;
  final List<SharedMediaFile> _sharedFiles = [];
  final AuthService _authService = AuthService();
  final ApiService _apiService = ApiService();
  List<HistoryItem> _history = [];
  bool _isLoading = false;
  GoogleSignInAccount? _currentUser;
  String? _authToken;
  ViewMode _currentView = ViewMode.all;
  String? _currentTypeFilter;

  @override
  void initState() {
    super.initState();
    _initAuth();
  }

  Future<void> _initAuth() async {
    await _authService.init();
    await _checkSignIn();
    _initSharingListeners();
  }

  Future<void> _checkSignIn() async {
    final user = await _authService.getCurrentUser();
    setState(() {
      _currentUser = user;
    });
    if (user != null) {
      _loadHistory();
    }
  }

  Future<void> _loadHistory() async {
    if (_currentUser == null) return;
    
    setState(() {
      _isLoading = true;
    });

    try {
      final authHeaders = await _currentUser!.authentication;
      final token = authHeaders.accessToken;
      if (token != null) {
        final items = await _apiService.fetchHistory(token);
        setState(() {
          _history = items;
          _authToken = token;
        });
      }
    } catch (e) {
      print('Error loading history: $e');
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to load history: $e')),
        );
      }
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }
  
  Future<void> _handleShare(List<SharedMediaFile> files, {String? text, String? fileName, int? fileSize, int? width, int? height, double? duration}) async {
    if (_currentUser == null) {
        // Require authentication - no offline support
        if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Please sign in to share items')),
            );
        }
        return;
    }

    try {
        final authHeaders = await _currentUser!.authentication;
        final token = authHeaders.accessToken;
        if (token == null) {
            return;
        }

        setState(() {
            _isLoading = true;
        });

        if (files.isNotEmpty) {
            // Handle file share (image/video/audio/file)
            final file = files.first;

            ShareItemType type = ShareItemType.file;
            if (file.type == SharedMediaType.image) type = ShareItemType.image;
            if (file.type == SharedMediaType.video) type = ShareItemType.video;

            await _apiService.uploadShare(
                token,
                type,
                file.path,
                _currentUser!.email,
                files: files,
                fileName: fileName,
                fileSize: fileSize,
                width: width,
                height: height,
                duration: duration,
            );
        } else if (text != null) {
            // Handle text/link share
            ShareItemType type = ShareItemType.text;
            if (text.startsWith('http://') || text.startsWith('https://')) {
                type = ShareItemType.webUrl;
            }

            await _apiService.uploadShare(token, type, text, _currentUser!.email);
        }

        // Refresh history
        await _loadHistory();

        if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Item shared successfully!')),
            );
        }

    } catch (e) {
        print('Error sharing item: $e');
        if (mounted) {
            ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Failed to share: $e')),
            );
        }
    } finally {
        setState(() {
            _isLoading = false;
            _sharedFiles.clear();
        });
    }
  }

  void _initSharingListeners() {
    // Initialize custom sharing service (iOS Share Extension)
    custom_sharing.SharingService().initialize();
    custom_sharing.SharingService().sharedContentStream.listen((items) {
      if (!mounted) return;
      print("Custom Shared content received: ${items.length}");
      
      // Filter for media items
      final mediaItems = items.where((i) => 
          i.type == custom_sharing.SharedMediaType.image || 
          i.type == custom_sharing.SharedMediaType.video || 
          i.type == custom_sharing.SharedMediaType.file
      ).toList();

      if (mediaItems.isNotEmpty) {
          // Prioritize Media: Use the first item for metadata, but pass all files?
          // Existing logic handles list of files but singular metadata.
          // Let's pass all files.
          
          List<SharedMediaFile> files = [];
          for (var item in mediaItems) {
              SharedMediaType type = SharedMediaType.file;
              if (item.type == custom_sharing.SharedMediaType.image) type = SharedMediaType.image;
              if (item.type == custom_sharing.SharedMediaType.video) type = SharedMediaType.video;
              
              files.add(SharedMediaFile(
                  path: item.value,
                  type: type,
                  thumbnail: item.thumbnail,
                  duration: item.duration?.toInt(),
              ));
          }
          
          // Use metadata from the first item
          final mainItem = mediaItems.first;
          
          _handleShare(
              files, 
              fileName: mainItem.fileName,
              fileSize: mainItem.fileSize,
              width: mainItem.width,
              height: mainItem.height,
              duration: mainItem.duration,
          );
      } else {
          // Fallback to Text/URL
          final textItem = items.where((i) => 
              i.type == custom_sharing.SharedMediaType.text || 
              i.type == custom_sharing.SharedMediaType.weburl
          ).firstOrNull;
          
          if (textItem != null) {
              _handleShare([], text: textItem.value);
          }
      }
    });

    // For sharing images, text, and files coming from outside the app while the app is in the memory
    _intentDataStreamSubscription = ReceiveSharingIntent.instance.getMediaStream().listen((List<SharedMediaFile> value) {
      if (!mounted) return;
      print("Shared content received (stream): ${value.length}");
      
      // Check if any shared item is text/url
      final textItem = value.where((f) => f.type == SharedMediaType.text || f.type == SharedMediaType.url).firstOrNull;
      
      if (textItem != null) {
          _handleShare([], text: textItem.path);
      } else if (value.isNotEmpty) {
          _handleShare(value);
      }
    }, onError: (err) {
      print("getMediaStream error: $err");
    });

    // For sharing images, text, and files coming from outside the app while the app is closed
    ReceiveSharingIntent.instance.getInitialMedia().then((List<SharedMediaFile> value) {
      if (!mounted) return;
      print("Shared content received (initial): ${value.length}");
      
      final textItem = value.where((f) => f.type == SharedMediaType.text || f.type == SharedMediaType.url).firstOrNull;

      if (textItem != null) {
           _handleShare([], text: textItem.path);
      } else if (value.isNotEmpty) {
           _handleShare(value);
      }
      
      if (value.isNotEmpty) {
           ReceiveSharingIntent.instance.reset();
      }
    });
  }

  @override
  void dispose() {
    _intentDataStreamSubscription?.cancel();
    super.dispose();
  }

  Future<void> _handleSignIn() async {
    try {
      final user = await _authService.signIn();
      setState(() {
        _currentUser = user;
      });
      if (user != null) {
          _loadHistory();
      }
    } catch (error) {
      print(error);
    }
  }

  Future<void> _handleSignOut() async {
    await _authService.signOut();
    setState(() {
      _currentUser = null;
      _history = [];
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          if (_currentUser != null)
            IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _loadHistory,
              tooltip: 'Refresh',
            ),
          if (_currentUser != null)
            IconButton(
              icon: const Icon(Icons.logout),
              onPressed: _handleSignOut,
              tooltip: 'Logout',
            ),
        ],
      ),
      body: _currentUser == null ? _buildSignInView() : _buildMainView(),
    );
  }

  Widget _buildSignInView() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.share_outlined,
              size: 64,
              color: AppColors.primary,
            ),
            const SizedBox(height: AppSpacing.xl),
            Text(
              'Analyze This',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              'Sign in to view and manage your shared items',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: AppColors.textSecondary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: AppSpacing.xxl),
            ElevatedButton.icon(
              onPressed: _handleSignIn,
              icon: const Icon(Icons.login),
              label: const Text('Sign in with Google'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMainView() {
    return Column(
      children: [
        // User header
        Container(
          padding: const EdgeInsets.all(AppSpacing.lg),
          color: AppColors.surface,
          child: Row(
            children: [
              if (_currentUser!.photoUrl != null)
                CircleAvatar(
                  radius: 20,
                  backgroundImage: NetworkImage(_currentUser!.photoUrl!),
                ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Welcome back,',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                    Text(
                      _currentUser!.displayName ?? 'User',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const Divider(height: 1),

        // Filter controls
        _buildFilterControls(),

        // Content
        Expanded(
          child: _isLoading
              ? Center(
                  child: CircularProgressIndicator(
                    color: AppColors.primary,
                  ),
                )
              : _getFilteredItems().isEmpty
                  ? _buildEmptyState()
                  : _buildHistoryList(),
        ),
      ],
    );
  }

  Widget _buildFilterControls() {
    return Container(
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.lg,
        vertical: AppSpacing.md,
      ),
      decoration: BoxDecoration(
        color: AppColors.surface,
        border: Border(
          bottom: BorderSide(color: Colors.grey.shade200),
        ),
      ),
      child: Row(
        children: [
          // View mode segmented button
          Flexible(
            child: SegmentedButton<ViewMode>(
              segments: const [
                ButtonSegment(value: ViewMode.all, label: Text('All')),
                ButtonSegment(value: ViewMode.timeline, label: Text('Timeline')),
                ButtonSegment(value: ViewMode.followUp, label: Text('Follow-up')),
              ],
              selected: {_currentView},
              onSelectionChanged: (Set<ViewMode> selection) {
                setState(() {
                  _currentView = selection.first;
                });
              },
            ),
          ),
          const SizedBox(width: AppSpacing.sm),
          // Type filter dropdown
          DropdownMenu<String?>(
            initialSelection: _currentTypeFilter,
            hintText: 'All Types',
            width: 120,
            onSelected: (String? value) {
              setState(() {
                _currentTypeFilter = value;
              });
            },
            dropdownMenuEntries: const [
              DropdownMenuEntry(value: null, label: 'All Types'),
              DropdownMenuEntry(value: 'image', label: 'Image'),
              DropdownMenuEntry(value: 'video', label: 'Video'),
              DropdownMenuEntry(value: 'audio', label: 'Audio'),
              DropdownMenuEntry(value: 'file', label: 'File'),
              DropdownMenuEntry(value: 'screenshot', label: 'Screenshot'),
              DropdownMenuEntry(value: 'text', label: 'Text'),
              DropdownMenuEntry(value: 'web_url', label: 'Web URL'),
            ],
          ),
        ],
      ),
    );
  }

  DateTime? _getEventDateTime(HistoryItem item) {
    if (item.analysis == null) return null;
    final details = item.analysis!['details'] as Map<String, dynamic>?;
    if (details == null) return null;

    final dateTimeStr = details['date_time'] ??
                        details['dateTime'] ??
                        details['date'] ??
                        details['event_date'] ??
                        details['eventDate'] ??
                        details['start_date'];

    if (dateTimeStr == null) return null;

    try {
      return DateTime.parse(dateTimeStr.toString());
    } catch (e) {
      return null;
    }
  }

  List<HistoryItem> _getFilteredItems() {
    List<HistoryItem> items = List.from(_history);

    // Apply type filter
    if (_currentTypeFilter != null) {
      items = items.where((item) => item.type == _currentTypeFilter).toList();
    }

    // Apply view-specific filtering and sorting
    switch (_currentView) {
      case ViewMode.timeline:
        items = items.where((item) => _getEventDateTime(item) != null).toList();
        items.sort((a, b) {
          final dateA = _getEventDateTime(a)!;
          final dateB = _getEventDateTime(b)!;
          return dateA.compareTo(dateB);
        });
        break;
      case ViewMode.followUp:
        items = items.where((item) => item.status == 'follow_up').toList();
        items.sort((a, b) => b.timestamp.compareTo(a.timestamp));
        break;
      case ViewMode.all:
        items.sort((a, b) => b.timestamp.compareTo(a.timestamp));
        break;
    }

    return items;
  }

  Widget _buildEmptyState() {
    String message;
    IconData icon;

    switch (_currentView) {
      case ViewMode.timeline:
        message = 'No items with event dates found';
        icon = Icons.event_outlined;
        break;
      case ViewMode.followUp:
        message = 'No items need follow-up';
        icon = Icons.check_circle_outline;
        break;
      case ViewMode.all:
        if (_currentTypeFilter != null) {
          message = 'No $_currentTypeFilter items found';
          icon = Icons.filter_list_off;
        } else {
          message = 'No items yet';
          icon = Icons.inbox_outlined;
        }
        break;
    }

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: 48,
              color: AppColors.textSecondary,
            ),
            const SizedBox(height: AppSpacing.lg),
            Text(
              message,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: AppSpacing.sm),
            Text(
              _currentView == ViewMode.all && _currentTypeFilter == null
                  ? 'Share content from other apps to see it here'
                  : 'Try changing your filters',
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildHistoryList() {
    final items = _getFilteredItems();

    if (_currentView == ViewMode.timeline) {
      return _buildTimelineList(items);
    }

    return ListView.builder(
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: items.length,
      itemBuilder: (context, index) {
        final item = items[index];
        return Padding(
          padding: EdgeInsets.only(
            bottom: index < items.length - 1 ? AppSpacing.md : 0,
          ),
          child: HistoryCard(
            item: item,
            authToken: _authToken,
            onTap: () => _openDetailFiltered(items, index),
            onDelete: () => _deleteItem(item),
          ),
        );
      },
    );
  }

  Widget _buildNowDivider() {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
      child: Row(
        children: [
          Expanded(
            child: Container(
              height: 2,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFF3b82f6), Color(0xFF8b5cf6)],
                ),
              ),
            ),
          ),
          Container(
            margin: const EdgeInsets.symmetric(horizontal: AppSpacing.md),
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.lg,
              vertical: AppSpacing.xs,
            ),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF3b82f6), Color(0xFF8b5cf6)],
              ),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Text(
              'NOW',
              style: TextStyle(
                color: Colors.white,
                fontSize: 12,
                fontWeight: FontWeight.w600,
                letterSpacing: 0.5,
              ),
            ),
          ),
          Expanded(
            child: Container(
              height: 2,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [Color(0xFF8b5cf6), Color(0xFF3b82f6)],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEventDateBadge(DateTime eventDate) {
    final dateStr = DateFormat('E, MMM d, h:mm a').format(eventDate);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.md,
        vertical: AppSpacing.sm,
      ),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.blue.shade50, Colors.purple.shade50],
        ),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
      ),
      child: Text(
        dateStr,
        style: TextStyle(
          color: Colors.indigo.shade600,
          fontSize: 12,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  Widget _buildTimelineList(List<HistoryItem> items) {
    final now = DateTime.now();
    int nowIndex = items.length; // Default: Now at end

    // Find where to insert Now divider
    for (int i = 0; i < items.length; i++) {
      final eventDate = _getEventDateTime(items[i]);
      if (eventDate != null && eventDate.isAfter(now)) {
        nowIndex = i;
        break;
      }
    }

    // Total items = items + 1 for Now divider
    final totalCount = items.length + 1;

    return ListView.builder(
      padding: const EdgeInsets.all(AppSpacing.lg),
      itemCount: totalCount,
      itemBuilder: (context, index) {
        // Insert Now divider at the right position
        if (index == nowIndex) {
          return _buildNowDivider();
        }

        // Adjust item index based on Now divider position
        final itemIndex = index > nowIndex ? index - 1 : index;
        final item = items[itemIndex];
        final eventDate = _getEventDateTime(item);

        return Padding(
          padding: EdgeInsets.only(
            bottom: index < totalCount - 1 ? AppSpacing.md : 0,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (eventDate != null) _buildEventDateBadge(eventDate),
              HistoryCard(
                item: item,
                authToken: _authToken,
                onTap: () => _openDetailFiltered(items, itemIndex),
                onDelete: () => _deleteItem(item),
              ),
            ],
          ),
        );
      },
    );
  }

  void _openDetailFiltered(List<HistoryItem> items, int index) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => ItemDetailScreen(
          items: items,
          initialIndex: index,
          authToken: _authToken,
        ),
      ),
    );
  }

  Future<void> _deleteItem(HistoryItem item) async {
    try {
      final authHeaders = await _currentUser!.authentication;
      final token = authHeaders.accessToken;
      if (token != null) {
        await _apiService.deleteItem(token, item.id);
        _loadHistory();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to delete: $e')),
        );
      }
    }
  }
}
