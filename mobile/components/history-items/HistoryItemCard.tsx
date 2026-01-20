import { StyleSheet, TouchableOpacity, View } from 'react-native';
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
    case 'webUrl':
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
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <ThemedText type="defaultSemiBold" style={styles.dateText}>
            {new Date(item.timestamp).toLocaleString()}
          </ThemedText>
          {item.analysis && (
            <Ionicons name="sparkles" size={14} color="#FFD700" />
          )}
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
        <TouchableOpacity style={styles.shareButton} onPress={() => onShare(item)}>
          <Ionicons name="share-outline" size={18} color="#0a7ea4" />
          <ThemedText style={styles.shareText}>Share</ThemedText>
        </TouchableOpacity>
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
