import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState, useRef } from 'react';
import { Alert } from 'react-native';
import { ShareIntent } from 'expo-share-intent';
import { useAuth } from '@/context/AuthContext';
import { API_URL } from '@/constants/Config';

export type ShareItemType = 'text' | 'web_url' | 'image' | 'video' | 'audio' | 'file' | 'screenshot';

export interface ShareItemMetadata {
    fileName?: string;
    mimeType?: string;
    fileSize?: number;
    duration?: number;
    width?: number;
    height?: number;
}

export interface HistoryItem {
    id: string;
    timestamp: number;
    value: string;
    type: ShareItemType;
    originalIntent?: ShareIntent;
    firestore_id?: string;
    title?: string;
    metadata?: ShareItemMetadata;
    analysis?: {
        overview: string;
        action?: string;
        details?: Record<string, unknown>;
        tags?: string[];
    };
}


const STORAGE_KEY = 'share_history_v1';

export function useShareHistory() {
    const { user } = useAuth();
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [isSyncing, setIsSyncing] = useState(false);

    const normalizeShareType = useCallback((rawType: string | null | undefined, value: string, metadata?: ShareItemMetadata): ShareItemType => {
        const normalized = (rawType || '').toLowerCase();

        if (normalized === 'weburl' || normalized === 'web_url') {
            return 'web_url';
        }

        const mimeType = metadata?.mimeType;
        if (mimeType) {
            if (mimeType.startsWith('image/')) return 'image';
            if (mimeType.startsWith('video/')) return 'video';
            if (mimeType.startsWith('audio/')) return 'audio';
        }

        if (normalized === 'file') {
            return 'file';
        }

        if (normalized === 'image' || normalized === 'video' || normalized === 'audio' || normalized === 'screenshot' || normalized === 'text') {
            return normalized as ShareItemType;
        }

        if (value) {
            const lowerValue = value.toLowerCase();
            if (lowerValue.match(/\.(png|jpe?g|gif|webp|bmp|tiff|svg)$/)) return 'image';
            if (lowerValue.match(/\.(mp4|mov|m4v|webm|avi|mkv)$/)) return 'video';
            if (lowerValue.match(/\.(mp3|wav|m4a|aac|flac|ogg)$/)) return 'audio';
        }

        if (normalized === 'media') {
            return 'image';
        }

        return 'text';
    }, []);

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
                    const mappedItems: HistoryItem[] = data.map((item: any) => {
                        const value = item.content || (item as any).value || '';
                        const metadata = item.item_metadata as ShareItemMetadata | undefined;
                        return {
                            id: item.firestore_id,
                            timestamp: new Date(item.created_at).getTime(),
                            value,
                            type: normalizeShareType(item.type, value, metadata),
                            firestore_id: item.firestore_id,
                            title: item.title,
                            metadata,
                            analysis: item.analysis,
                        };
                    });
                    setHistory(mappedItems);
                } else {
                    console.error('Failed to fetch from backend');
                }
            } else {
                // Load from Local Storage
                const jsonValue = await AsyncStorage.getItem(STORAGE_KEY);
                if (jsonValue != null) {
                    const parsed = JSON.parse(jsonValue) as HistoryItem[];
                    const normalized = parsed.map((item) => ({
                        ...item,
                        type: normalizeShareType(item.type, item.value, item.metadata),
                    }));
                    setHistory(normalized);
                }
            }
        } catch (e) {
            console.error('Failed to load history', e);
        } finally {
            setIsLoading(false);
            setIsSyncing(false);
        }
    }, [user, normalizeShareType]);

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
            let type: ShareItemType = 'text';
            let value = '';
            let title: string | undefined;
            let metadata: ShareItemMetadata | undefined;

            if (intent.webUrl) {
                value = intent.webUrl;
                title = intent.meta?.title;
                type = normalizeShareType('web_url', value);
            } else if (intent.text) {
                value = intent.text;
                title = intent.meta?.title;
                type = normalizeShareType('text', value);
            } else if (intent.files && intent.files.length > 0) {
                // @ts-ignore
                const file = intent.files[0];
                // @ts-ignore
                const mimeType = file.mimeType || intent.type || '';
                // @ts-ignore
                const fileName = file.fileName || file.name;

                metadata = {
                    fileName,
                    mimeType,
                    // @ts-ignore
                    fileSize: file.size || file.fileSize,
                    // @ts-ignore
                    duration: file.duration,
                    // @ts-ignore
                    width: file.width,
                    // @ts-ignore
                    height: file.height,
                };

                // @ts-ignore
                value = file.path || file.uri || file.filePath || file.contentUri || 'File';
                title = fileName || intent.meta?.title;
                type = normalizeShareType(intent.type, value, metadata);
            }

            console.log(`Processed share item: type=${type}, value=${value}`);

            const newItem: HistoryItem = {
                id: Date.now().toString() + Math.random().toString(36).substr(2, 9),
                timestamp: Date.now(),
                type,
                value,
                originalIntent: intent,
                title,
                metadata,
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

                    if (intent.files && intent.files.length > 0) {
                        const formData = new FormData();
                        formData.append('title', title || 'From Mobile');
                        formData.append('content', value); // Will be replaced by URL on backend, but good to send original path too? or backend ignore?
                        formData.append('type', type);
                        formData.append('user_email', user.email);

                        // Append file
                        // @ts-ignore
                        const file = intent.files[0];
                        // @ts-ignore
                        const mimeType = metadata?.mimeType || file.mimeType || 'application/octet-stream';
                        // @ts-ignore
                        const fileName = metadata?.fileName || file.fileName || file.name || `upload_${Date.now()}`;

                        // @ts-ignore
                        formData.append('file', {
                            uri: value, // value is URI from previous step
                            name: fileName,
                            type: mimeType,
                        } as any);

                        if (metadata?.fileName) formData.append('file_name', metadata.fileName);
                        if (metadata?.mimeType) formData.append('mime_type', metadata.mimeType);
                        if (metadata?.fileSize) formData.append('file_size', metadata.fileSize.toString());
                        if (metadata?.duration) formData.append('duration', metadata.duration.toString());
                        if (metadata?.width) formData.append('width', metadata.width.toString());
                        if (metadata?.height) formData.append('height', metadata.height.toString());

                        body = formData;
                        // Content-Type is handled automatically by fetch for FormData
                    } else {
                        headers['Content-Type'] = 'application/json';
                        body = JSON.stringify({
                            title: title || 'From Mobile',
                            content: value,
                            type: type,
                            user_email: user.email,
                            item_metadata: metadata,
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
        [saveHistory, user, loadHistory, normalizeShareType]
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
