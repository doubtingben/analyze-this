import { Image } from 'expo-image';
import { StyleSheet, FlatList, TouchableOpacity, Share, View, Alert, TextInput, RefreshControl, ActivityIndicator } from 'react-native';
import { useShareIntent } from 'expo-share-intent';
import { useEffect, useCallback, useState, useRef } from 'react';
import { useFocusEffect } from 'expo-router';

import { HelloWave } from '@/components/hello-wave';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { useShareHistory, HistoryItem } from '@/hooks/useShareHistory';
import { MediaHistoryItem, WebUrlHistoryItem, TextHistoryItem, FileHistoryItem } from '@/components/history-items';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '@/context/AuthContext';

export default function HomeScreen() {
  const { hasShareIntent, shareIntent, resetShareIntent } = useShareIntent();
  const { history, addToHistory, removeItem, loadHistory, isSyncing, isLoading } = useShareHistory();
  const { user, signIn, signInDev, signOut } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');

  useFocusEffect(
    useCallback(() => {
      loadHistory();
    }, [loadHistory])
  );

  const processingRef = useRef(false);

  const lastProcessedRef = useRef<string | null>(null);

  useEffect(() => {
    if (hasShareIntent && shareIntent && !processingRef.current) {
      // Deduplicate based on content signature
      const signature = JSON.stringify({
        text: shareIntent.text,
        webUrl: shareIntent.webUrl,
        type: shareIntent.type,
        // @ts-ignore - access path safely or fallback
        files: shareIntent.files?.map(f => f.path ?? '')
      });

      if (lastProcessedRef.current === signature) {
        // Already processing or processed this exact intent
        return;
      }

      if (shareIntent.type === 'text' || shareIntent.type === 'weburl' || (shareIntent.files && shareIntent.files.length > 0)) {
        processingRef.current = true;
        lastProcessedRef.current = signature;

        (async () => {
          try {
            await addToHistory(shareIntent);
          } catch (e) {
            console.error("Error adding to history:", e);
          } finally {
            resetShareIntent(); // Clear intent after adding
            processingRef.current = false;
            // We do NOT clear lastProcessedRef here to prevent re-processing until intent is cleared externally
          }
        })();
      }
    } else if (!hasShareIntent) {
      processingRef.current = false;
      lastProcessedRef.current = null;
    }
  }, [hasShareIntent, shareIntent, addToHistory, resetShareIntent]);

  const handleShare = async (item: HistoryItem) => {
    try {
      await Share.share({
        message: item.value,
        url: item.type === 'web_url' ? item.value : undefined,
      });
    } catch (error: any) {
      Alert.alert(error.message);
    }
  };

  const filteredHistory = history.filter(item =>
    item.value.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const renderItem = ({ item }: { item: HistoryItem }) => {
    switch (item.type) {
      case 'image':
      case 'screenshot':
      case 'image':
        return <MediaHistoryItem item={item} onDelete={removeItem} onShare={handleShare} />;
      case 'video':
      case 'audio':
      case 'file':
        return <FileHistoryItem item={item} onDelete={removeItem} onShare={handleShare} />;
      case 'web_url':
        return <WebUrlHistoryItem item={item} onDelete={removeItem} onShare={handleShare} />;
      case 'text':
      default:
        return <TextHistoryItem item={item} onDelete={removeItem} onShare={handleShare} />;
    }
  };

  return (
    <ThemedView style={styles.container}>
      <FlatList
        data={filteredHistory}
        keyExtractor={(item, index) => item.id ? `${item.id}-${index}` : `item-${index}`}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl refreshing={isLoading} onRefresh={loadHistory} />
        }
        ListHeaderComponent={
          <>
            <View style={styles.header}>
              <Image
                source={require('@/assets/images/partial-react-logo.png')}
                style={styles.reactLogo}
              />
              <View style={styles.headerContent}>
                <View style={styles.titleContainer}>
                  <ThemedText type="title">Analyze This</ThemedText>
                  <HelloWave />
                </View>
                <View style={{ flexDirection: 'row', gap: 8 }}>
                  {__DEV__ && !user && (
                    <TouchableOpacity onPress={signInDev} style={[styles.authButton, { backgroundColor: '#666' }]}>
                      <Ionicons name="construct-outline" size={20} color="white" />
                      <ThemedText style={styles.authButtonText}>Dev</ThemedText>
                    </TouchableOpacity>
                  )}
                  <TouchableOpacity onPress={user ? signOut : signIn} style={styles.authButton}>
                    <Ionicons name={user ? "log-out-outline" : "logo-google"} size={20} color="white" />
                    <ThemedText style={styles.authButtonText}>{user ? 'Logout' : 'Login'}</ThemedText>
                  </TouchableOpacity>
                </View>
              </View>
            </View>

            <View style={styles.controlsContainer}>
              <ThemedView style={styles.searchContainer}>
                <Ionicons name="search" size={20} color="#888" style={{ marginRight: 8 }} />
                <TextInput
                  style={styles.searchInput}
                  placeholder="Search items..."
                  placeholderTextColor="#888"
                  value={searchQuery}
                  onChangeText={setSearchQuery}
                />
              </ThemedView>
            </View>

            <ThemedView style={styles.sectionHeader}>
              <ThemedText type="subtitle">
                {user ? 'My Cloud Items' : 'Local History'}
              </ThemedText>
              <ThemedText>{filteredHistory.length} items</ThemedText>
              {isSyncing && (
                <View style={styles.syncContainer}>
                  <ActivityIndicator size="small" color="#0a7ea4" />
                  <ThemedText style={styles.syncText}>Syncing...</ThemedText>
                </View>
              )}
            </ThemedView>

            {filteredHistory.length === 0 && (
              <View style={styles.emptyState}>
                <ThemedText style={styles.emptyStateText}>
                  {searchQuery ? 'No matches found.' : 'No shared items yet.'}
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
    marginBottom: 0,
  },
  headerContent: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-end',
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
  authButton: {
    backgroundColor: '#0a7ea4',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6
  },
  authButtonText: {
    color: 'white',
    fontWeight: '600'
  },
  controlsContainer: {
    padding: 16,
    backgroundColor: 'transparent',
  },
  searchContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(128,128,128, 0.1)',
    borderRadius: 10,
    paddingHorizontal: 12,
    height: 40,
  },
  searchInput: {
    flex: 1,
    height: '100%',
    color: '#000', // Adjust for theme if needed
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
  emptyState: {
    padding: 32,
    alignItems: 'center',
  },
  emptyStateText: {
    textAlign: 'center',
    opacity: 0.6,
  },
  syncContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  syncText: {
    fontSize: 12,
    opacity: 0.7,
  }
});
