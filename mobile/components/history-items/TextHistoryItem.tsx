import { StyleSheet } from 'react-native';
import { ThemedText } from '@/components/themed-text';
import { HistoryItem } from '@/hooks/useShareHistory';
import { HistoryItemCard } from './HistoryItemCard';

interface TextHistoryItemProps {
  item: HistoryItem;
  onDelete: (id: string) => void;
  onShare: (item: HistoryItem) => void;
}

export function TextHistoryItem({ item, onDelete, onShare }: TextHistoryItemProps) {
  return (
    <HistoryItemCard item={item} onDelete={onDelete} onShare={onShare}>
      <ThemedText style={styles.content} numberOfLines={3}>
        {item.value}
      </ThemedText>
    </HistoryItemCard>
  );
}

const styles = StyleSheet.create({
  content: {
    marginBottom: 12,
  },
});
