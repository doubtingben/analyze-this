import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState, useRef } from 'react';
import { Alert } from 'react-native';
import { ShareIntent } from 'expo-share-intent';
import { useAuth } from '@/context/AuthContext';
import { API_URL } from '@/constants/Config';

export interface HistoryItem {
    id: string;
    timestamp: number;
    value: string;
    type: 'text' | 'web_url' | 'media' | 'file' | 'screenshot';
    originalIntent?: ShareIntent;
    firestore_id?: string;
    title?: string;
}

const STORAGE_KEY = 'share_history_v1';

export function useShareHistory() {
    const { user } = useAuth();
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSyncing, setIsSyncing] = useState(false);

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
                        firestore_id: item.firestore_id,
                        title: item.title
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
            setIsSyncing(false);
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

    const historyRef = useRef(history);
    useEffect(() => {
        historyRef.current = history;
    }, [history]);

    const addToHistory = useCallback(
        async (intent: ShareIntent) => {
            console.log("Received share intent:", JSON.stringify(intent, null, 2));
            let type: HistoryItem['type'] = 'text';
            let value = '';

            if (intent.webUrl) {
                type = 'web_url';
                value = intent.webUrl;
            } else if (intent.text) {
                type = 'text';
                value = intent.text;
            } else if (intent.files && intent.files.length > 0) {
                // @ts-ignore
                const file = intent.files[0];
                // @ts-ignore
                const mimeType = file.mimeType || intent.type;

                if (mimeType && mimeType.startsWith('image/')) {
                    type = 'media';
                } else {
                    type = 'file';
                }

                // @ts-ignore
                value = file.path || file.uri || 'File';
            }

            console.log(`Processed share item: type=${type}, value=${value}`);

            const newItem: HistoryItem = {
                id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
                timestamp: Date.now(),
                type,
                value,
                originalIntent: intent,
            };

            const currentHistory = historyRef.current;

            if (user && user.idToken) {
                // Sync to Backend
                try {
                    console.log("Syncing to backend...");
                    let body;
                    let headers: Record<string, string> = {
                        'Authorization': `Bearer ${user.idToken}`
                    };
                    setIsSyncing(true);

                    if (type === 'media') {
                        const formData = new FormData();
                        formData.append('title', 'From Mobile');
                        formData.append('content', value); // Will be replaced by URL on backend, but good to send original path too? or backend ignore?
                        formData.append('type', type);
                        formData.append('user_email', user.email);

                        // Append file
                        // @ts-ignore
                        const file = intent.files[0];
                        // @ts-ignore
                        const mimeType = file.mimeType || 'image/jpeg';
                        // @ts-ignore
                        const fileName = file.fileName || file.name || `upload_${Date.now()}`;

                        // @ts-ignore
                        formData.append('file', {
                            uri: value, // value is URI from previous step
                            name: fileName,
                            type: mimeType,
                        } as any);

                        body = formData;
                        // Content-Type is handled automatically by fetch for FormData
                    } else {
                        headers['Content-Type'] = 'application/json';
                        body = JSON.stringify({
                            title: 'From Mobile',
                            content: value,
                            type: type,
                            user_email: user.email,
                        });
                    }

                    const response = await fetch(`${API_URL}/api/share`, {
                        method: 'POST',
                        headers: headers,
                        body: body
                    });

                    if (response.ok) {
                        console.log("Backend sync successful");
                        // Reload to get the new ID and correct timestamp
                        loadHistory();
                    } else {
                        const errorText = await response.text();
                        console.error("Backend sync failed:", response.status, errorText);
                        Alert.alert(`Failed to save to cloud: ${response.status}`);
                        // Fallback to local
                        const newHistory = [newItem, ...currentHistory];
                        setHistory(newHistory);
                    }
                } catch (e) {
                    console.error("Failed to sync item", e);
                    Alert.alert(`Network error saving item: ${e}`);
                    // Fallback to local
                    const newHistory = [newItem, ...currentHistory];
                    setHistory(newHistory);
                } finally {
                    setIsSyncing(false);
                }
            } else {
                console.log("No user logged in, saving locally");
                const newHistory = [newItem, ...currentHistory];
                await saveHistory(newHistory);
            }
        },
        [saveHistory, user, loadHistory]
    );

    const removeItem = useCallback(
        async (id: string) => {
            if (user && user.idToken) {
                try {
                    setIsSyncing(true);
                    await fetch(`${API_URL}/api/items/${id}`, {
                        method: 'DELETE',
                        headers: {
                            'Authorization': `Bearer ${user.idToken}`
                        }
                    });
                    loadHistory();
                } catch (e) {
                    console.error("Failed to delete", e);
                } finally {
                    setIsSyncing(false);
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
        isSyncing,
    };
}
