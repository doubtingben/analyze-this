import { StyleSheet, TouchableOpacity, View, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { HistoryItem } from '@/hooks/useShareHistory';

interface HistoryItemCardProps {
  item: HistoryItem;
  onDelete: (id: string) => void;
  onShare: (item: HistoryItem) => void;
  children: React.ReactNode;
  badgeColor?: { bg: string; text: string };
}

const getBadgeColor = (type: HistoryItem['type']) => {
  switch (type) {
    case 'media':
      return { bg: 'rgba(76, 175, 80, 0.2)', text: '#4CAF50' };
    case 'screenshot':
      return { bg: 'rgba(156, 39, 176, 0.2)', text: '#9C27B0' };
    case 'web_url':
      return { bg: 'rgba(33, 150, 243, 0.2)', text: '#2196F3' };
    case 'file':
      return { bg: 'rgba(255, 152, 0, 0.2)', text: '#FF9800' };
    case 'text':
    default:
      return { bg: 'rgba(128, 128, 128, 0.2)', text: '#888' };
  }
};

export function HistoryItemCard({ item, onDelete, onShare, children, badgeColor }: HistoryItemCardProps) {
  const colors = badgeColor ?? getBadgeColor(item.type);

  return (
    <ThemedView style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={{ flex: 1, marginRight: 8 }}>
          {item.title ? (
            <ThemedText type="defaultSemiBold" numberOfLines={1}>{item.title}</ThemedText>
          ) : null}
          <ThemedText style={styles.dateText}>
            {new Date(item.timestamp).toLocaleString()}
          </ThemedText>
        </View>
        <TouchableOpacity onPress={() => onDelete(item.id)}>
          <Ionicons name="trash-outline" size={20} color="#ff4444" />
        </TouchableOpacity>
      </View>

      {children}

      <View style={styles.cardFooter}>
        <ThemedText style={[styles.typeBadge, { backgroundColor: colors.bg, color: colors.text }]}>
          {item.type.toUpperCase()}
        </ThemedText>

        <View style={styles.actionButtons}>
          {/* Analysis Sparkle */}
          <TouchableOpacity
            onPress={() => item.analysis ? Alert.alert('Analysis', item.analysis.overview) : null}
            activeOpacity={item.analysis ? 0.7 : 1}
          >
            <Ionicons
              name="sparkles"
              size={20}
              color={item.analysis ? "#FFD700" : "#ccc"}
            />
          </TouchableOpacity>

          <TouchableOpacity style={styles.shareButton} onPress={() => onShare(item)}>
            <Ionicons name="share-outline" size={18} color="#0a7ea4" />
            <ThemedText style={styles.shareText}>Share</ThemedText>
          </TouchableOpacity>
        </View>
      </View>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  card: {
    marginHorizontal: 16,
    marginBottom: 12,
    padding: 16,
    borderRadius: 12,
    backgroundColor: 'rgba(128,128,128, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(128,128,128, 0.2)',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  dateText: {
    fontSize: 12,
    opacity: 0.7,
  },
  cardFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: 'rgba(128,128,128, 0.1)',
    paddingTop: 8,
  },
  typeBadge: {
    fontSize: 10,
    fontWeight: 'bold',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    overflow: 'hidden',
  },
  actionButtons: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 16,
  },
  shareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  shareText: {
    color: '#0a7ea4',
    fontSize: 14,
    fontWeight: '600',
  },
});
