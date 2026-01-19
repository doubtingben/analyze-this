import { StyleSheet, TouchableOpacity, View } from 'react-native';
import { Image } from 'expo-image';
import { openBrowserAsync } from 'expo-web-browser';
import { Ionicons } from '@expo/vector-icons';
import { ThemedText } from '@/components/themed-text';
import { HistoryItem } from '@/hooks/useShareHistory';
import { HistoryItemCard } from './HistoryItemCard';

interface WebUrlHistoryItemProps {
  item: HistoryItem;
  onDelete: (id: string) => void;
  onShare: (item: HistoryItem) => void;
}

const extractDomain = (url: string): string => {
  try {
    const urlObj = new URL(url);
    return urlObj.hostname.replace('www.', '');
  } catch {
    return url;
  }
};

export function WebUrlHistoryItem({ item, onDelete, onShare }: WebUrlHistoryItemProps) {
  const domain = extractDomain(item.value);
  const faviconUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;

  const handlePress = async () => {
    try {
      await openBrowserAsync(item.value);
    } catch (error) {
      console.error('Failed to open URL:', error);
    }
  };

  return (
    <HistoryItemCard item={item} onDelete={onDelete} onShare={onShare}>
      <TouchableOpacity style={styles.urlContainer} onPress={handlePress} activeOpacity={0.7}>
        <Image
          source={{ uri: faviconUrl }}
          style={styles.favicon}
          contentFit="contain"
          cachePolicy="memory-disk"
        />
        <View style={styles.urlTextContainer}>
          <ThemedText style={styles.domain}>{domain}</ThemedText>
          <ThemedText style={styles.fullUrl} numberOfLines={1}>
            {item.value}
          </ThemedText>
        </View>
        <Ionicons name="open-outline" size={18} color="#0a7ea4" style={styles.linkIcon} />
      </TouchableOpacity>
    </HistoryItemCard>
  );
}

const styles = StyleSheet.create({
  urlContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: 'rgba(33, 150, 243, 0.08)',
    borderRadius: 8,
  },
  favicon: {
    width: 24,
    height: 24,
    marginRight: 12,
    borderRadius: 4,
  },
  urlTextContainer: {
    flex: 1,
  },
  domain: {
    fontSize: 16,
    fontWeight: '600',
    color: '#0a7ea4',
  },
  fullUrl: {
    fontSize: 12,
    opacity: 0.7,
    marginTop: 2,
  },
  linkIcon: {
    marginLeft: 8,
  },
});
