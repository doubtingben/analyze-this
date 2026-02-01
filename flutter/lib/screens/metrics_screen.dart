import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../theme/app_colors.dart';
import '../theme/app_spacing.dart';

class MetricsScreen extends StatefulWidget {
  final String authToken;

  const MetricsScreen({super.key, required this.authToken});

  @override
  State<MetricsScreen> createState() => _MetricsScreenState();
}

class _MetricsScreenState extends State<MetricsScreen> {
  final ApiService _apiService = ApiService();
  bool _isLoading = true;
  String? _error;
  int _totalItems = 0;
  Map<String, int> _statusCounts = {};
  int _totalWorkerJobs = 0;
  Map<String, int> _workerStatusCounts = {};

  // Display names for item statuses
  static const Map<String, String> _statusLabels = {
    'new': 'New',
    'analyzing': 'Analyzing',
    'analyzed': 'Analyzed',
    'timeline': 'Timeline',
    'follow_up': 'Follow-up',
    'processed': 'Processed',
    'soft_deleted': 'Archived',
  };

  // Icons for item statuses
  static const Map<String, IconData> _statusIcons = {
    'new': Icons.fiber_new,
    'analyzing': Icons.hourglass_top,
    'analyzed': Icons.check_circle_outline,
    'timeline': Icons.event,
    'follow_up': Icons.flag,
    'processed': Icons.done_all,
    'soft_deleted': Icons.archive,
  };

  // Colors for item statuses
  static const Map<String, Color> _statusColors = {
    'new': Colors.blue,
    'analyzing': Colors.orange,
    'analyzed': Colors.teal,
    'timeline': Colors.purple,
    'follow_up': Colors.amber,
    'processed': Colors.green,
    'soft_deleted': Colors.grey,
  };

  // Display names for worker queue statuses (from backend WorkerJobStatus enum)
  static const Map<String, String> _workerStatusLabels = {
    'queued': 'Queued',
    'leased': 'Processing',
    'completed': 'Completed',
    'failed': 'Failed',
  };

  // Icons for worker queue statuses (from backend WorkerJobStatus enum)
  static const Map<String, IconData> _workerStatusIcons = {
    'queued': Icons.schedule,
    'leased': Icons.sync,
    'completed': Icons.check_circle,
    'failed': Icons.error_outline,
  };

  // Colors for worker queue statuses (from backend WorkerJobStatus enum)
  static const Map<String, Color> _workerStatusColors = {
    'queued': Colors.blue,
    'leased': Colors.orange,
    'completed': Colors.green,
    'failed': Colors.red,
  };

  @override
  void initState() {
    super.initState();
    _loadMetrics();
  }

  Future<void> _loadMetrics() async {
    setState(() {
      _isLoading = true;
      _error = null;
    });

    try {
      final metrics = await _apiService.getMetrics(widget.authToken);
      setState(() {
        _totalItems = metrics['total_items'] as int? ?? 0;
        final byStatus = metrics['by_status'] as Map<String, dynamic>? ?? {};
        _statusCounts = byStatus.map((key, value) => MapEntry(key, value as int));

        // Parse worker queue metrics
        final workerQueue = metrics['worker_queue'] as Map<String, dynamic>? ?? {};
        _totalWorkerJobs = workerQueue['total'] as int? ?? 0;
        final workerByStatus = workerQueue['by_status'] as Map<String, dynamic>? ?? {};
        _workerStatusCounts = workerByStatus.map((key, value) => MapEntry(key, value as int));

        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Metrics'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadMetrics,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return Center(
        child: CircularProgressIndicator(color: AppColors.primary),
      );
    }

    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.error_outline, size: 48, color: Colors.red.shade400),
              const SizedBox(height: AppSpacing.lg),
              Text(
                'Failed to load metrics',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: AppSpacing.sm),
              Text(
                _error!,
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: AppSpacing.lg),
              ElevatedButton.icon(
                onPressed: _loadMetrics,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadMetrics,
      child: ListView(
        padding: const EdgeInsets.all(AppSpacing.lg),
        children: [
          // Total items card
          _buildTotalCard(),
          const SizedBox(height: AppSpacing.xl),

          // Status breakdown header
          Text(
            'Items by Status',
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: AppSpacing.md),

          // Status cards
          ..._buildStatusCards(),

          // Worker queue section (always show)
          const SizedBox(height: AppSpacing.xl),
          _buildWorkerQueueSection(),
        ],
      ),
    );
  }

  Widget _buildTotalCard() {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          children: [
            Icon(
              Icons.inventory_2_outlined,
              size: 48,
              color: AppColors.primary,
            ),
            const SizedBox(height: AppSpacing.md),
            Text(
              '$_totalItems',
              style: Theme.of(context).textTheme.displaySmall?.copyWith(
                fontWeight: FontWeight.bold,
                color: AppColors.primary,
              ),
            ),
            Text(
              'Total Items',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                color: AppColors.textSecondary,
              ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildStatusCards() {
    // Order statuses in a logical flow
    const statusOrder = [
      'new',
      'analyzing',
      'analyzed',
      'timeline',
      'follow_up',
      'processed',
      'soft_deleted',
    ];

    final widgets = <Widget>[];

    for (final status in statusOrder) {
      final count = _statusCounts[status] ?? 0;
      if (count > 0 || status == 'new' || status == 'follow_up') {
        // Always show new and follow_up even if 0
        widgets.add(_buildStatusCard(status, count));
        widgets.add(const SizedBox(height: AppSpacing.sm));
      }
    }

    // Add any statuses that aren't in our predefined order
    for (final entry in _statusCounts.entries) {
      if (!statusOrder.contains(entry.key) && entry.value > 0) {
        widgets.add(_buildStatusCard(entry.key, entry.value));
        widgets.add(const SizedBox(height: AppSpacing.sm));
      }
    }

    return widgets;
  }

  Widget _buildStatusCard(String status, int count) {
    final label = _statusLabels[status] ?? status;
    final icon = _statusIcons[status] ?? Icons.circle;
    final color = _statusColors[status] ?? Colors.grey;

    return Card(
      child: ListTile(
        leading: Container(
          padding: const EdgeInsets.all(AppSpacing.sm),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: color),
        ),
        title: Text(label),
        trailing: Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.xs,
          ),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            '$count',
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
              fontSize: 16,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildWorkerQueueSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Worker queue header with total
        Row(
          children: [
            Icon(Icons.work_outline, color: AppColors.textSecondary),
            const SizedBox(width: AppSpacing.sm),
            Text(
              'Worker Queue',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const Spacer(),
            Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.md,
                vertical: AppSpacing.xs,
              ),
              decoration: BoxDecoration(
                color: AppColors.primary.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                '$_totalWorkerJobs jobs',
                style: TextStyle(
                  color: AppColors.primary,
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: AppSpacing.md),

        // Worker status cards
        ..._buildWorkerStatusCards(),
      ],
    );
  }

  List<Widget> _buildWorkerStatusCards() {
    const statusOrder = ['queued', 'leased', 'completed', 'failed'];
    final widgets = <Widget>[];

    for (final status in statusOrder) {
      final count = _workerStatusCounts[status] ?? 0;
      // Always show queued and leased (active jobs), hide completed/failed if 0
      if (count > 0 || status == 'queued' || status == 'leased') {
        widgets.add(_buildWorkerStatusCard(status, count));
        widgets.add(const SizedBox(height: AppSpacing.sm));
      }
    }

    // Add any statuses not in our predefined order
    for (final entry in _workerStatusCounts.entries) {
      if (!statusOrder.contains(entry.key) && entry.value > 0) {
        widgets.add(_buildWorkerStatusCard(entry.key, entry.value));
        widgets.add(const SizedBox(height: AppSpacing.sm));
      }
    }

    return widgets;
  }

  Widget _buildWorkerStatusCard(String status, int count) {
    final label = _workerStatusLabels[status] ?? status;
    final icon = _workerStatusIcons[status] ?? Icons.circle;
    final color = _workerStatusColors[status] ?? Colors.grey;

    return Card(
      child: ListTile(
        leading: Container(
          padding: const EdgeInsets.all(AppSpacing.sm),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(icon, color: color),
        ),
        title: Text(label),
        trailing: Container(
          padding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.md,
            vertical: AppSpacing.xs,
          ),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Text(
            '$count',
            style: TextStyle(
              color: color,
              fontWeight: FontWeight.bold,
              fontSize: 16,
            ),
          ),
        ),
      ),
    );
  }
}
