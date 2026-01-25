import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { HistoryItem } from '@/hooks/useShareHistory';
import { HistoryItemCard } from './HistoryItemCard';
import { ThemedText } from '@/components/themed-text';

interface FileHistoryItemProps {
  item: HistoryItem;
  onDelete: (id: string) => void;
  onShare: (item: HistoryItem) => void;
}

const getIconName = (type: HistoryItem['type']) => {
  switch (type) {
    case 'video':
      return 'videocam-outline';
    case 'audio':
      return 'musical-notes-outline';
    case 'image':
    case 'screenshot':
      return 'image-outline';
    case 'file':
    default:
      return 'document-outline';
  }
};

const formatFileSize = (size?: number) => {
  if (!size || Number.isNaN(size)) return null;
  const kb = size / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
};

export function FileHistoryItem({ item, onDelete, onShare }: FileHistoryItemProps) {
  const label = item.title || item.metadata?.fileName || item.value || 'Shared file';
  const sizeLabel = formatFileSize(item.metadata?.fileSize);
  const details = [item.metadata?.mimeType, sizeLabel].filter(Boolean).join(' • ');

  return (
    <HistoryItemCard item={item} onDelete={onDelete} onShare={onShare}>
      <View style={styles.container}>
        <View style={styles.iconWrapper}>
          <Ionicons name={getIconName(item.type)} size={24} color="#0a7ea4" />
        </View>
        <View style={styles.textWrapper}>
          <ThemedText type="defaultSemiBold" numberOfLines={1}>
            {label}
          </ThemedText>
          {details ? (
            <ThemedText style={styles.detailsText} numberOfLines={1}>
              {details}
            </ThemedText>
          ) : null}
        </View>
      </View>
    </HistoryItemCard>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 12,
  },
  iconWrapper: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(10, 126, 164, 0.12)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  textWrapper: {
    flex: 1,
  },
  detailsText: {
    fontSize: 12,
    opacity: 0.7,
    marginTop: 2,
  },
});
