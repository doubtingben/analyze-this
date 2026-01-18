import { Image } from 'expo-image';
import { StyleSheet, FlatList, TouchableOpacity, Share, View, Alert, TextInput } from 'react-native';
import { useShareIntent } from 'expo-share-intent';
import { useEffect, useCallback, useState, useRef } from 'react';
import { useFocusEffect } from 'expo-router';

import { HelloWave } from '@/components/hello-wave';
import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { useShareHistory, HistoryItem } from '@/hooks/useShareHistory';
import { Ionicons } from '@expo/vector-icons';
import { useAuth } from '@/context/AuthContext';

export default function HomeScreen() {
  const { hasShareIntent, shareIntent, resetShareIntent } = useShareIntent();
  const { history, addToHistory, removeItem, loadHistory } = useShareHistory();
  const { user, signIn, signOut } = useAuth();
  const [searchQuery, setSearchQuery] = useState('');

  useFocusEffect(
    useCallback(() => {
      loadHistory();
    }, [loadHistory])
  );

  const processingRef = useRef(false);

  useEffect(() => {
    if (hasShareIntent && shareIntent && !processingRef.current) {
      if (shareIntent.type === 'text' || shareIntent.type === 'weburl' || (shareIntent.files && shareIntent.files.length > 0)) {
        processingRef.current = true;
        (async () => {
          await addToHistory(shareIntent);
          resetShareIntent(); // Clear intent after adding
          processingRef.current = false;
        })();
      }
    } else if (!hasShareIntent) {
      processingRef.current = false;
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

  const filteredHistory = history.filter(item =>
    item.value.toLowerCase().includes(searchQuery.toLowerCase())
  );

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
      <FlatList
        data={filteredHistory}
        keyExtractor={(item, index) => item.id ? `${item.id}-${index}` : `item-${index}`}
        renderItem={renderItem}
        contentContainerStyle={styles.listContent}
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
                <TouchableOpacity onPress={user ? signOut : signIn} style={styles.authButton}>
                  <Ionicons name={user ? "log-out-outline" : "logo-google"} size={20} color="white" />
                  <ThemedText style={styles.authButtonText}>{user ? 'Logout' : 'Login'}</ThemedText>
                </TouchableOpacity>
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
