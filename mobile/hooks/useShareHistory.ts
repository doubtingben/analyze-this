import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';
import { ShareIntent } from 'expo-share-intent';
import { useAuth } from '@/context/AuthContext';
import { API_URL } from '@/constants/Config';

export interface HistoryItem {
    id: string;
    timestamp: number;
    value: string;
    type: 'text' | 'webUrl' | 'media' | 'file';
    originalIntent?: ShareIntent;
    firestore_id?: string;
}

const STORAGE_KEY = 'share_history_v1';

export function useShareHistory() {
    const { user } = useAuth();
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const loadHistory = useCallback(async () => {
        setIsLoading(true);
        try {
            if (user && user.idToken) {
                // Load from Backend
                const response = await fetch(`${API_URL}/api/items`, {
                    headers: {
                        'Authorization': `Bearer ${user.idToken}`
                    }
                });
                if (response.ok) {
                    const data = await response.json();
                    // map backend data to HistoryItem
                    const mappedItems: HistoryItem[] = data.map((item: any) => ({
                        id: item.firestore_id,
                        timestamp: new Date(item.created_at).getTime(),
                        value: item.content || (item as any).value, // support both schemas if they differ
                        type: item.type,
                        firestore_id: item.firestore_id
                    }));
                    setHistory(mappedItems);
                } else {
                    console.error('Failed to fetch from backend');
                }
            } else {
                // Load from Local Storage
                const jsonValue = await AsyncStorage.getItem(STORAGE_KEY);
                if (jsonValue != null) {
                    setHistory(JSON.parse(jsonValue));
                }
            }
        } catch (e) {
            console.error('Failed to load history', e);
        } finally {
            setIsLoading(false);
        }
    }, [user]);

    const saveHistory = useCallback(async (newHistory: HistoryItem[]) => {
        try {
            await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(newHistory));
            setHistory(newHistory);
        } catch (e) {
            console.error('Failed to save history', e);
        }
    }, []);

    const addToHistory = useCallback(
        async (intent: ShareIntent) => {
            let type: HistoryItem['type'] = 'text';
            let value = '';

            if (intent.webUrl) {
                type = 'webUrl';
                value = intent.webUrl;
            } else if (intent.text) {
                type = 'text';
                value = intent.text;
            } else if (intent.files && intent.files.length > 0) {
                type = 'file';
                // @ts-ignore
                value = intent.files[0].path || intent.files[0].uri || 'File';
            }

            const newItem: HistoryItem = {
                id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
                timestamp: Date.now(),
                type,
                value,
                originalIntent: intent,
            };

            if (user && user.idToken) {
                // Sync to Backend
                try {
                    const response = await fetch(`${API_URL}/api/share`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${user.idToken}`
                        },
                        body: JSON.stringify({
                            title: 'From Mobile', // Optional
                            content: value,
                            type: type,
                            // created_at handled by backend or we send it? Backend timestamp is better usually.
                            // Looking at backend models.py would clarify, but let's assume basic fields. 
                            // The backend main.py shows SharedItem model.
                        })
                    });
                    if (response.ok) {
                        // Reload to get the new ID and correct timestamp
                        loadHistory();
                    }
                } catch (e) {
                    console.error("Failed to sync item", e);
                    // Fallback to local? Or show error? For now, let's just add to local view locally
                    const newHistory = [newItem, ...history];
                    setHistory(newHistory); // Optimistic update could be complex with sync.
                }
            } else {
                const newHistory = [newItem, ...history];
                await saveHistory(newHistory);
            }
        },
        [history, saveHistory, user, loadHistory]
    );

    const removeItem = useCallback(
        async (id: string) => {
            if (user && user.idToken) {
                try {
                    await fetch(`${API_URL}/api/items/${id}`, {
                        method: 'DELETE',
                        headers: {
                            'Authorization': `Bearer ${user.idToken}`
                        }
                    });
                    loadHistory();
                } catch (e) {
                    console.error("Failed to delete", e);
                }
            } else {
                const newHistory = history.filter((item) => item.id !== id);
                await saveHistory(newHistory);
            }
        },
        [history, saveHistory, user, loadHistory]
    );

    const clearHistory = useCallback(async () => {
        if (!user) {
            await saveHistory([]);
        }
    }, [saveHistory, user]);

    useEffect(() => {
        loadHistory();
    }, [loadHistory]);

    return {
        history,
        isLoading,
        loadHistory,
        addToHistory,
        removeItem,
        clearHistory,
    };
}
