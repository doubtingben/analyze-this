import { Image, StyleSheet, View } from 'react-native';
import { HistoryItem } from '@/hooks/useShareHistory';
import { useAuth } from '../../context/AuthContext';
import { HistoryItemCard } from './HistoryItemCard';

console.log('MediaHistoryItem loaded, useAuth:', useAuth);

interface MediaHistoryItemProps {
  item: HistoryItem;
  onDelete: (id: string) => void;
  onShare: (item: HistoryItem) => void;
}

export function MediaHistoryItem({ item, onDelete, onShare }: MediaHistoryItemProps) {
  const { user } = useAuth();

  const imageSource = {
    uri: item.value,
    headers: user?.idToken ? { Authorization: `Bearer ${user.idToken}` } : undefined
  };

  console.log('Rendering MediaHistoryItem:', item.id);
  console.log('Image Source URI:', item.value);
  console.log('Has Auth Token:', !!user?.idToken);

  return (
    <HistoryItemCard item={item} onDelete={onDelete} onShare={onShare}>
      <View style={styles.imageContainer}>
        <Image
          source={imageSource}
          style={styles.image}
          resizeMode="cover"
          onLoadStart={() => console.log('Image load start:', item.value)}
          onLoad={() => console.log('Image loaded successfully:', item.value)}
          onError={(e) => console.error('Image load failed:', item.value, e.nativeEvent.error)}
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
