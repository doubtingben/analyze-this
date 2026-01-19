import { StyleSheet, View } from 'react-native';
import { Image } from 'expo-image';
import { HistoryItem } from '@/hooks/useShareHistory';
import { HistoryItemCard } from './HistoryItemCard';

interface MediaHistoryItemProps {
  item: HistoryItem;
  onDelete: (id: string) => void;
  onShare: (item: HistoryItem) => void;
}

export function MediaHistoryItem({ item, onDelete, onShare }: MediaHistoryItemProps) {
  return (
    <HistoryItemCard item={item} onDelete={onDelete} onShare={onShare}>
      <View style={styles.imageContainer}>
        <Image
          source={{ uri: item.value }}
          style={styles.image}
          contentFit="cover"
          transition={200}
          cachePolicy="memory-disk"
        />
      </View>
    </HistoryItemCard>
  );
}

const styles = StyleSheet.create({
  imageContainer: {
    width: '100%',
    height: 180,
    borderRadius: 8,
    overflow: 'hidden',
    marginBottom: 12,
    backgroundColor: 'rgba(128,128,128,0.1)',
  },
  image: {
    width: '100%',
    height: '100%',
  },
});
