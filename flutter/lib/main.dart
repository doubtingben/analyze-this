import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:intl/intl.dart';
import 'package:timezone/data/latest.dart' as tz;
import 'package:timezone/timezone.dart' as tz;
import 'package:url_launcher/url_launcher.dart';

import 'auth_service.dart';
import 'services/api_service.dart';
import 'models/history_item.dart';
import 'theme/app_theme.dart';
import 'theme/app_colors.dart';
import 'theme/app_spacing.dart';
import 'widgets/history_card.dart';
import 'widgets/filter_dialog.dart';
import 'screens/item_detail_screen.dart';
import 'screens/metrics_screen.dart';
import 'screens/tag_editor_screen.dart';

import 'services/sharing_service.dart' as custom_sharing;

enum ViewMode { all, timeline, followUp, media }

const Set<String> _mediaTags = {'to_read', 'to_listen', 'to_watch'};

void main() {
  tz.initializeTimeZones();
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
  tz.Location? _userTimezoneLocation;
  ViewMode _currentView = ViewMode.all;
  Set<String> _selectedTypes = {};     // Empty = all types
  Set<String> _selectedTags = {};      // Empty = no tag filter
  String _searchQuery = '';            // Empty = no search
  bool _showHidden = false;
  bool _searchExpanded = false;

  // Active filter count for badge
  int get _activeFilterCount => _selectedTypes.length + _selectedTags.length;

  // Search controller
  final TextEditingController _searchController = TextEditingController();
  final FocusNode _searchFocusNode = FocusNode();

  // Timeline scroll state
  final ScrollController _timelineScrollController = ScrollController();
  final GlobalKey _nowDividerKey = GlobalKey();
  int _nowListIndex = 0; // Index of Now divider in the list
  bool _hasScrolledToNow = false;
  bool _nowButtonVisible = false;
  bool _nowIsAbove = false; // true = Now is above viewport, false = Now is below

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

        // Fetch note counts for all items
        final itemIds = items.map((item) => item.id).toList();
        if (itemIds.isNotEmpty) {
          try {
            final noteCounts = await _apiService.getNoteCounts(token, itemIds);
            // Update items with note counts
            final itemsWithCounts = items.map((item) {
              final count = noteCounts[item.id] ?? 0;
              return item.copyWith(noteCount: count);
            }).toList();
            setState(() {
              _history = itemsWithCounts;
              _authToken = token;
            });
          } catch (e) {
            // If note counts fail, still show items without counts
            print('Warning: Failed to load note counts: $e');
            setState(() {
              _history = items;
              _authToken = token;
            });
          }
        } else {
          setState(() {
            _history = items;
            _authToken = token;
          });
        }
        
        // Fetch user profile for timezone
        try {
          final profile = await _apiService.getUserProfile(token);
          if (profile.containsKey('timezone')) {
             final tzName = profile['timezone'] as String;
             try {
               setState(() {
                 _userTimezoneLocation = tz.getLocation(tzName);
               });
             } catch (e) {
               print('Invalid timezone from profile: $tzName');
               // Fallback to EST if invalid, or keep default
               try {
                 setState(() {
                    _userTimezoneLocation = tz.getLocation('America/New_York');
                 });
               } catch (_) {}
             }
          }
        } catch (e) {
          print('Failed to fetch user profile: $e');
        }

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
    _timelineScrollController.dispose();
    _searchController.dispose();
    _searchFocusNode.dispose();
    super.dispose();
  }

  void _updateNowVisibility() {
    if (_nowDividerKey.currentContext == null) return;

    final RenderBox? nowBox = _nowDividerKey.currentContext?.findRenderObject() as RenderBox?;
    if (nowBox == null || !nowBox.hasSize) return;

    // Get the Now divider's position relative to the screen
    final nowPosition = nowBox.localToGlobal(Offset.zero);
    final screenHeight = MediaQuery.of(context).size.height;

    // Account for app bar and filter controls (roughly 250px from top)
    const topOffset = 250.0;
    const bottomPadding = 100.0;

    final nowY = nowPosition.dy;
    final isVisible = nowY >= topOffset && nowY <= screenHeight - bottomPadding;
    final isAbove = nowY < topOffset;

    if (_nowButtonVisible != !isVisible || _nowIsAbove != isAbove) {
      setState(() {
        _nowButtonVisible = !isVisible;
        _nowIsAbove = isAbove;
      });
    }
  }

  void _scrollToNow({bool animate = true}) {
    if (!_timelineScrollController.hasClients) return;

    // Try using Scrollable.ensureVisible if context is available
    if (_nowDividerKey.currentContext != null) {
      Scrollable.ensureVisible(
        _nowDividerKey.currentContext!,
        duration: animate ? const Duration(milliseconds: 300) : Duration.zero,
        curve: Curves.easeInOut,
        alignment: 0.3, // Position Now at 30% from top of viewport
      ).then((_) {
        if (mounted) _updateNowVisibility();
      });
      return;
    }

    // Fallback: estimate position based on index
    // Average item height is roughly 200px (card + padding + date badge)
    const estimatedItemHeight = 200.0;
    final targetOffset = _nowListIndex * estimatedItemHeight;
    final maxScroll = _timelineScrollController.position.maxScrollExtent;
    final clampedOffset = targetOffset.clamp(0.0, maxScroll);

    if (animate) {
      _timelineScrollController.animateTo(
        clampedOffset,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      ).then((_) {
        if (mounted) _updateNowVisibility();
      });
    } else {
      _timelineScrollController.jumpTo(clampedOffset);
      Future.delayed(const Duration(milliseconds: 50), () {
        if (mounted) _updateNowVisibility();
      });
    }
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

  void _openMetrics() {
    if (_authToken == null) return;

    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => MetricsScreen(authToken: _authToken!),
      ),
    );
  }

  void _openTagEditor() {
    if (_authToken == null) return;
    Navigator.pop(context); // Close the menu
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => TagEditorScreen(
          authToken: _authToken!,
          items: _history,
        ),
      ),
    ).then((_) {
      _loadHistory(); // Refresh in case tags were deleted
    });
  }

  void _toggleSearch() {
    setState(() {
      if (_searchExpanded) {
        // Collapse: clear search and close
        _searchController.clear();
        _searchQuery = '';
        _searchExpanded = false;
      } else {
        // Expand and focus
        _searchExpanded = true;
        Future.microtask(() => _searchFocusNode.requestFocus());
      }
    });
  }

  void _showFilterDialog() {
    FilterDialog.show(
      context: context,
      selectedTypes: _selectedTypes,
      selectedTags: _selectedTags,
      availableTags: _getAllAvailableTags(),
      onApply: (types, tags) {
        setState(() {
          _selectedTypes = types;
          _selectedTags = tags;
        });
      },
    );
  }

  Future<void> _handleExport() async {
    if (_currentUser == null) return;

    try {
      final authHeaders = await _currentUser!.authentication;
      final token = authHeaders.accessToken;
      if (token == null) return;

      final bytes = await _apiService.exportData(token);
      final timestamp = DateFormat('yyyyMMdd_HHmmss').format(DateTime.now());
      final file = File(
        '${Directory.systemTemp.path}/analyze-this-export-$timestamp.zip',
      );
      await file.writeAsBytes(bytes, flush: true);

      final uri = Uri.file(file.path);
      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
      } else if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Export saved to ${file.path}')),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Export failed: $e')),
        );
      }
    }
  }

  void _showUserMenu() {
    if (_currentUser == null) return;

    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.lg),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: _currentUser!.photoUrl != null
                      ? CircleAvatar(
                          backgroundImage: NetworkImage(_currentUser!.photoUrl!),
                        )
                      : const CircleAvatar(child: Icon(Icons.person)),
                  title: Text(_currentUser!.displayName ?? 'User'),
                  subtitle: Text(_currentUser!.email),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Show Archive'),
                  value: _showHidden,
                  onChanged: (value) {
                    setState(() {
                      _showHidden = value;
                    });
                    Navigator.pop(context);
                  },
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.analytics_outlined),
                  title: const Text('Metrics'),
                  onTap: () {
                    Navigator.pop(context);
                    _openMetrics();
                  },
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.label_outline),
                  title: const Text('Tag Editor'),
                  onTap: _openTagEditor,
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.download),
                  title: const Text('Export'),
                  onTap: () {
                    Navigator.pop(context);
                    _handleExport();
                  },
                ),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.logout),
                  title: const Text('Logout'),
                  onTap: () {
                    Navigator.pop(context);
                    _handleSignOut();
                  },
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: _currentUser != null
            ? Padding(
                padding: const EdgeInsets.all(8.0),
                child: GestureDetector(
                  onTap: _showUserMenu,
                  child: _currentUser!.photoUrl != null
                      ? CircleAvatar(
                          backgroundImage: NetworkImage(_currentUser!.photoUrl!),
                        )
                      : const CircleAvatar(child: Icon(Icons.person, size: 20)),
                ),
              )
            : null,
        title: _searchExpanded
            ? TextField(
                controller: _searchController,
                focusNode: _searchFocusNode,
                decoration: InputDecoration(
                  hintText: 'Search...',
                  border: InputBorder.none,
                  suffixIcon: IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: _toggleSearch,
                  ),
                ),
                onChanged: (value) => setState(() => _searchQuery = value),
              )
            : Text(widget.title),
        actions: _currentUser != null
            ? [
                if (!_searchExpanded)
                  IconButton(
                    icon: Icon(
                      Icons.search,
                      color: _searchQuery.isNotEmpty ? AppColors.primary : null,
                    ),
                    onPressed: _toggleSearch,
                    tooltip: 'Search',
                  ),
                Badge(
                  isLabelVisible: _activeFilterCount > 0,
                  label: Text('$_activeFilterCount'),
                  child: IconButton(
                    icon: const Icon(Icons.filter_list),
                    onPressed: _showFilterDialog,
                    tooltip: 'Filter',
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.refresh),
                  onPressed: _loadHistory,
                  tooltip: 'Refresh',
                ),
              ]
            : null,
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
        // Filter controls (view mode tabs)
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
      child: Center(
        child: SegmentedButton<ViewMode>(
          showSelectedIcon: false,
          segments: const [
            ButtonSegment(value: ViewMode.all, label: Text('All')),
            ButtonSegment(value: ViewMode.timeline, label: Text('Timeline')),
            ButtonSegment(value: ViewMode.followUp, label: Text('Follow-up')),
            ButtonSegment(value: ViewMode.media, label: Text('Media')),
          ],
          selected: {_currentView},
          onSelectionChanged: (Set<ViewMode> selection) {
            setState(() {
              _currentView = selection.first;
            });
          },
        ),
      ),
    );
  }

  DateTime? _getEventDateTime(HistoryItem item) {
    if (item.analysis == null) return null;

    // Check for new 'timeline' structure
    final timeline = item.analysis!['timeline'] as Map<String, dynamic>?;
    if (timeline != null) {
      final dateStr = timeline['date'];
      final timeStr = timeline['time'];
      
      if (dateStr != null) {
        try {
          if (timeStr != null && timeStr != "null") {
            // Attempt to combine date and time
            final dateTimeStr = "$dateStr $timeStr";
            if (_userTimezoneLocation != null) {
              return tz.TZDateTime.parse(_userTimezoneLocation!, dateTimeStr);
            }
            return DateTime.parse(dateTimeStr);
          }
          if (_userTimezoneLocation != null) {
             return tz.TZDateTime.parse(_userTimezoneLocation!, dateStr);
          }
          return DateTime.parse(dateStr);
        } catch (_) {
          // Fall through to other checks if parsing fails
        }
      }
    }

    // Fallback to old 'details' structure
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
      if (_userTimezoneLocation != null) {
        return tz.TZDateTime.parse(_userTimezoneLocation!, dateTimeStr.toString());
      }
      return DateTime.parse(dateTimeStr.toString());
    } catch (e) {
      return null;
    }
  }

  Set<String> _getAllAvailableTags() {
    final tags = <String>{};
    for (final item in _history) {
      final itemTags = item.analysis?['tags'];
      if (itemTags is List) {
        tags.addAll(itemTags.cast<String>());
      }
    }
    return tags;
  }

  int? _getConsumptionTime(HistoryItem item) {
    final analysis = item.analysis;
    if (analysis == null) return null;
    final time = analysis['consumption_time_minutes'];
    if (time is int) return time;
    if (time is num) return time.toInt();
    return null;
  }

  bool _isFutureAvailability(HistoryItem item) {
    final eventDate = _getEventDateTime(item);
    if (eventDate == null) return false;
    return eventDate.isAfter(DateTime.now());
  }

  String _formatConsumptionTime(int minutes) {
    if (minutes < 60) return '~$minutes min';
    final hours = minutes / 60;
    if (hours < 10) return '~${hours.toStringAsFixed(1)} hr';
    return '~${hours.round()} hr';
  }

  Map<String, List<HistoryItem>> _groupItemsByMediaTag(List<HistoryItem> items) {
    final groups = <String, List<HistoryItem>>{
      'to_watch': [],
      'to_listen': [],
      'to_read': [],
    };

    for (final item in items) {
      final tags = item.analysis?['tags'];
      if (tags is! List) continue;
      for (final tag in _mediaTags) {
        if (tags.contains(tag)) {
          groups[tag]!.add(item);
        }
      }
    }

    // Sort each group by consumption time (nulls last), then by timestamp
    for (final group in groups.values) {
      group.sort((a, b) {
        final timeA = _getConsumptionTime(a);
        final timeB = _getConsumptionTime(b);
        if (timeA == null && timeB == null) return b.timestamp.compareTo(a.timestamp);
        if (timeA == null) return 1;
        if (timeB == null) return -1;
        return timeA.compareTo(timeB);
      });
    }

    return groups;
  }

  List<HistoryItem> _getFilteredItems() {
    List<HistoryItem> items = List.from(_history);

    if (!_showHidden) {
      items = items.where((item) => !item.isHidden).toList();
    }

    // Apply search filter
    if (_searchQuery.isNotEmpty) {
      final query = _searchQuery.toLowerCase();
      items = items.where((item) =>
        (item.title?.toLowerCase().contains(query) ?? false) ||
        item.value.toLowerCase().contains(query)
      ).toList();
    }

    // Apply type filter (multi-select)
    if (_selectedTypes.isNotEmpty) {
      items = items.where((item) => _selectedTypes.contains(item.type)).toList();
    }

    // Apply tag filter
    if (_selectedTags.isNotEmpty) {
      items = items.where((item) {
        final itemTags = item.analysis?['tags'];
        if (itemTags is! List) return false;
        return _selectedTags.any((tag) => itemTags.contains(tag));
      }).toList();
    }

    // Apply view-specific filtering and sorting
    switch (_currentView) {
      case ViewMode.timeline:
        items = items.where((item) => _getEventDateTime(item) != null).toList();
        items.sort((a, b) {
          final dateA = _getEventDateTime(a)!;
          final dateB = _getEventDateTime(b)!;
          return dateB.compareTo(dateA);
        });
        break;
      case ViewMode.followUp:
        items = items.where((item) => item.status == 'follow_up').toList();
        items.sort((a, b) => b.timestamp.compareTo(a.timestamp));
        break;
      case ViewMode.media:
        items = items.where((item) {
          final tags = item.analysis?['tags'];
          if (tags is! List) return false;
          return tags.any((t) => _mediaTags.contains(t));
        }).toList();
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

    if (!_showHidden && _history.any((item) => item.isHidden)) {
      message = 'No visible items';
      icon = Icons.visibility_off_outlined;
    } else {
    switch (_currentView) {
      case ViewMode.timeline:
        message = 'No items with event dates found';
        icon = Icons.event_outlined;
        break;
      case ViewMode.followUp:
        message = 'No items need follow-up';
        icon = Icons.check_circle_outline;
        break;
      case ViewMode.media:
        message = 'No media items found';
        icon = Icons.play_circle_outline;
        break;
      case ViewMode.all:
        if (_selectedTypes.isNotEmpty || _selectedTags.isNotEmpty || _searchQuery.isNotEmpty) {
          message = 'No matching items found';
          icon = Icons.filter_list_off;
        } else {
          message = 'No items yet';
          icon = Icons.inbox_outlined;
        }
        break;
    }
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
              (!_showHidden && _history.any((item) => item.isHidden))
                  ? 'Enable "Show Archive" to view archived items'
                  : _currentView == ViewMode.all && _selectedTypes.isEmpty && _selectedTags.isEmpty && _searchQuery.isEmpty
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

    if (_currentView == ViewMode.media) {
      return _buildMediaList(items);
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
            isHidden: item.isHidden,
            onToggleHidden: () => _setItemHidden(item, !item.isHidden),
            onTap: () => _openDetailFiltered(items, index),
            onDelete: () => _deleteItem(item),
          ),
        );
      },
    );
  }

  Widget _buildMediaList(List<HistoryItem> items) {
    final groups = _groupItemsByMediaTag(items);
    final sections = <Widget>[];

    const groupLabels = {
      'to_watch': 'To Watch',
      'to_listen': 'To Listen',
      'to_read': 'To Read',
    };

    for (final tag in ['to_watch', 'to_listen', 'to_read']) {
      final groupItems = groups[tag]!;
      if (groupItems.isEmpty) continue;

      // Section header
      sections.add(
        Padding(
          padding: const EdgeInsets.fromLTRB(0, 16, 0, 8),
          child: Text(
            groupLabels[tag]!,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
        ),
      );

      // Items in this group
      for (int i = 0; i < groupItems.length; i++) {
        final item = groupItems[i];
        final consumptionTime = _getConsumptionTime(item);
        final isFuture = _isFutureAvailability(item);

        sections.add(
          Padding(
            padding: EdgeInsets.only(bottom: i < groupItems.length - 1 ? AppSpacing.md : 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Badges row
                if (consumptionTime != null || isFuture)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Row(
                      children: [
                        if (consumptionTime != null)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.grey.shade100,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              _formatConsumptionTime(consumptionTime),
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey.shade700,
                              ),
                            ),
                          ),
                        if (consumptionTime != null && isFuture) const SizedBox(width: 6),
                        if (isFuture)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: Colors.purple.shade50,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              'Available ${DateFormat('MMM d').format(_getEventDateTime(item)!)}',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.purple.shade700,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                // The item card itself
                HistoryCard(
                  item: item,
                  authToken: _authToken,
                  isHidden: item.isHidden,
                  onToggleHidden: () => _setItemHidden(item, !item.isHidden),
                  onTap: () => _openDetailFiltered(items, items.indexOf(item)),
                  onDelete: () => _deleteItem(item),
                ),
              ],
            ),
          ),
        );
      }
    }

    if (sections.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.play_circle_outline, size: 48, color: AppColors.textSecondary),
              const SizedBox(height: AppSpacing.lg),
              Text('No media items found', style: Theme.of(context).textTheme.titleMedium),
            ],
          ),
        ),
      );
    }

    return ListView(
      padding: const EdgeInsets.all(AppSpacing.lg),
      children: sections,
    );
  }

  Widget _buildNowDivider() {
    return Padding(
      key: _nowDividerKey,
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
      if (eventDate != null && eventDate.isBefore(now)) {
        nowIndex = i;
        break;
      }
    }

    // Store for scroll calculations
    _nowListIndex = nowIndex;

    // Total items = items + 1 for Now divider
    final totalCount = items.length + 1;

    // Scroll to Now on first load (with delay to ensure widget is rendered)
    if (!_hasScrolledToNow && items.isNotEmpty) {
      _hasScrolledToNow = true;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        // Small delay to ensure GlobalKey context is available
        Future.delayed(const Duration(milliseconds: 100), () {
          if (mounted) {
            _scrollToNow(animate: false);
          }
        });
      });
    }

    // Add scroll listener for visibility tracking
    _timelineScrollController.removeListener(_updateNowVisibility);
    _timelineScrollController.addListener(_updateNowVisibility);

    // Update visibility after build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _updateNowVisibility();
    });

    final listView = ListView.builder(
      controller: _timelineScrollController,
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

        final isPastEvent = eventDate != null && eventDate.isBefore(now);
        final card = HistoryCard(
          item: item,
          authToken: _authToken,
          isHidden: item.isHidden,
          showImage: false,
          showDate: false,
          onToggleHidden: () => _setItemHidden(item, !item.isHidden),
          onTap: () => _openDetailFiltered(items, itemIndex),
          onDelete: () => _deleteItem(item),
        );

        final styledCard = isPastEvent
            ? Transform.scale(
                scale: 0.97,
                alignment: Alignment.topCenter,
                child: Opacity(
                  opacity: 0.7,
                  child: ColorFiltered(
                    colorFilter: const ColorFilter.matrix(<double>[
                      0.2126, 0.7152, 0.0722, 0, 0,
                      0.2126, 0.7152, 0.0722, 0, 0,
                      0.2126, 0.7152, 0.0722, 0, 0,
                      0,      0,      0,      1, 0,
                    ]),
                    child: card,
                  ),
                ),
              )
            : card;

        return Padding(
          padding: EdgeInsets.only(
            bottom: index < totalCount - 1 ? AppSpacing.md : 0,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (eventDate != null) _buildEventDateBadge(eventDate),
              styledCard,
            ],
          ),
        );
      },
    );

    return Stack(
      children: [
        listView,
        if (_nowButtonVisible)
          Positioned(
            left: 0,
            right: 0,
            top: _nowIsAbove ? AppSpacing.md : null,
            bottom: !_nowIsAbove ? AppSpacing.md : null,
            child: Center(
              child: _buildNowButton(),
            ),
          ),
      ],
    );
  }

  Widget _buildNowButton() {
    return GestureDetector(
      onTap: _scrollToNow,
      child: Container(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.lg,
          vertical: AppSpacing.sm,
        ),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFF3b82f6), Color(0xFF8b5cf6)],
          ),
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              _nowIsAbove ? Icons.arrow_upward : Icons.arrow_downward,
              color: Colors.white,
              size: 16,
            ),
            const SizedBox(width: AppSpacing.xs),
            const Text(
              'Now',
              style: TextStyle(
                color: Colors.white,
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _openDetailFiltered(List<HistoryItem> items, int index) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => ItemDetailScreen(
          items: items,
          initialIndex: index,
          authToken: _authToken,
          onItemUpdated: _handleItemUpdated,
        ),
      ),
    );
  }

  void _handleItemUpdated(HistoryItem updatedItem) {
    // Update the item in the local history list
    setState(() {
      _history = _history.map((item) {
        if (item.id == updatedItem.id) {
          return updatedItem;
        }
        return item;
      }).toList();
    });
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

  Future<void> _setItemHidden(HistoryItem item, bool hidden) async {
    try {
      final authHeaders = await _currentUser!.authentication;
      final token = authHeaders.accessToken;
      if (token != null) {
        await _apiService.setItemHidden(token, item.id, hidden);
        _loadHistory();
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to update visibility: $e')),
        );
      }
    }
  }
}
