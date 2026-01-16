import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';
import { ShareIntent } from 'expo-share-intent';

export interface HistoryItem {
    id: string;
    timestamp: number;
    value: string;
    type: 'text' | 'webUrl' | 'media' | 'file';
    originalIntent: ShareIntent;
}

const STORAGE_KEY = 'share_history_v1';

export function useShareHistory() {
    const [history, setHistory] = useState<HistoryItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    const loadHistory = useCallback(async () => {
        try {
            const jsonValue = await AsyncStorage.getItem(STORAGE_KEY);
            if (jsonValue != null) {
                setHistory(JSON.parse(jsonValue));
            }
        } catch (e) {
            console.error('Failed to load history', e);
        } finally {
            setIsLoading(false);
        }
    }, []);

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
            // Avoid duplicates based on timestamp/content if needed, 
            // but for now we just add everything.

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

            const newHistory = [newItem, ...history];
            await saveHistory(newHistory);
        },
        [history, saveHistory]
    );

    const removeItem = useCallback(
        async (id: string) => {
            const newHistory = history.filter((item) => item.id !== id);
            await saveHistory(newHistory);
        },
        [history, saveHistory]
    );

    const clearHistory = useCallback(async () => {
        await saveHistory([]);
    }, [saveHistory]);

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
