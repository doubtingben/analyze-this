import { Image } from 'expo-image';
import { Platform, StyleSheet, Button, FlatList, TouchableOpacity, Share, View, Alert } from 'react-native';
import { useShareIntent } from 'expo-share-intent';
import { useEffect, useCallback } from 'react';
import { useFocusEffect } from 'expo-router';

import { HelloWave } from '@/components/hello-wave';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { useShareHistory, HistoryItem } from '@/hooks/useShareHistory';
import { Ionicons } from '@expo/vector-icons';

export default function HomeScreen() {
  const { hasShareIntent, shareIntent, resetShareIntent } = useShareIntent();
  const { history, addToHistory, removeItem, loadHistory } = useShareHistory();

  useFocusEffect(
    useCallback(() => {
      loadHistory();
    }, [loadHistory])
  );

  useEffect(() => {
    if (hasShareIntent && shareIntent) {
      if (shareIntent.type === 'text' || shareIntent.type === 'weburl' || (shareIntent.files && shareIntent.files.length > 0)) {
        addToHistory(shareIntent);
        resetShareIntent(); // Clear intent after adding
      }
    }
  }, [hasShareIntent, shareIntent, addToHistory, resetShareIntent]);

  const handleShare = async (item: HistoryItem) => {
    try {
      await Share.share({
        message: item.value,
        url: item.type === 'webUrl' ? item.value : undefined,
      });
    } catch (error: any) {
      Alert.alert(error.message);
    }
  };

  const renderItem = ({ item }: { item: HistoryItem }) => (
    <ThemedView style={styles.card}>
      <View style={styles.cardHeader}>
        <ThemedText type="defaultSemiBold" style={styles.dateText}>
          {new Date(item.timestamp).toLocaleString()}
        </ThemedText>
        <TouchableOpacity onPress={() => removeItem(item.id)}>
          <Ionicons name="trash-outline" size={20} color="#ff4444" />
        </TouchableOpacity>
      </View>

      <ThemedText style={styles.cardContent} numberOfLines={3}>
        {item.value}
      </ThemedText>

      <View style={styles.cardFooter}>
        <ThemedText style={styles.typeBadge}>{item.type.toUpperCase()}</ThemedText>
        <TouchableOpacity style={styles.shareButton} onPress={() => handleShare(item)}>
          <Ionicons name="share-outline" size={18} color="#0a7ea4" />
          <ThemedText style={styles.shareText}>Share</ThemedText>
        </TouchableOpacity>
      </View>
    </ThemedView>
  );

  return (
    <ThemedView style={styles.container}>
      {/* Header Section mimicking original Parallax feel but static for FlatList header */}
      <FlatList
        data={history}
        keyExtractor={(item) => item.id}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
        ListHeaderComponent={
          <>
            <View style={styles.header}>
              <Image
                source={require('@/assets/images/partial-react-logo.png')}
                style={styles.reactLogo}
              />
              <View style={styles.titleContainer}>
                <ThemedText type="title">Analyze This</ThemedText>
                <HelloWave />
              </View>
            </View>

            <ThemedView style={styles.sectionHeader}>
              <ThemedText type="subtitle">Shared History</ThemedText>
              <ThemedText>{history.length} items</ThemedText>
            </ThemedView>

            {history.length === 0 && (
              <View style={styles.emptyState}>
                <ThemedText style={styles.emptyStateText}>
                  No shared items yet. Share content to the app to see it here.
                </ThemedText>
              </View>
            )}
          </>
        }
      />
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  header: {
    height: 250,
    backgroundColor: '#A1CEDC', // Light mode color
    justifyContent: 'flex-end',
    padding: 16,
    overflow: 'hidden',
    marginBottom: 16,
  },
  reactLogo: {
    height: 178,
    width: 290,
    bottom: 0,
    left: 0,
    position: 'absolute',
    opacity: 0.5,
  },
  titleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  sectionHeader: {
    paddingHorizontal: 16,
    marginBottom: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  listContent: {
    paddingBottom: 40,
  },
  card: {
    marginHorizontal: 16,
    marginBottom: 12,
    padding: 16,
    borderRadius: 12,
    backgroundColor: 'rgba(128,128,128, 0.1)', // Subtle background
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
  cardContent: {
    marginBottom: 12,
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
    backgroundColor: 'rgba(128,128,128, 0.2)',
    borderRadius: 4,
    overflow: 'hidden',
  },
  shareButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4
  },
  shareText: {
    color: '#0a7ea4',
    fontSize: 14,
    fontWeight: '600'
  },
  emptyState: {
    padding: 32,
    alignItems: 'center',
  },
  emptyStateText: {
    textAlign: 'center',
    opacity: 0.6,
  }
});
