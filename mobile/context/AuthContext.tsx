import { createContext, useContext, useState, useEffect } from 'react';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Linking from 'expo-linking';
import { ResponseType } from 'expo-auth-session';

WebBrowser.maybeCompleteAuthSession();

const STORAGE_KEY = 'auth_user';

interface User {
    email: string;
    name?: string;
    picture?: string;
    idToken?: string;
}

interface AuthContextType {
    user: User | null;
    signIn: () => void;
    signInDev?: () => void;
    signOut: () => void;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType>({
    user: null,
    signIn: () => { },
    signOut: () => { },
    isLoading: true,
});

export function useAuth() {
    return useContext(AuthContext);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    // Hardcoded fallback because process.env is sometimes unreliable in release builds context without extra config
    const GOOGLE_CLIENT_ID = process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID || '106064975526-5cirithftrku0j78rs8h9l34p7lf84kk.apps.googleusercontent.com';

    const [request, response, promptAsync] = Google.useAuthRequest({
        // Use the Web Client ID for all platforms to support HTTPS redirects
        clientId: GOOGLE_CLIENT_ID,
        iosClientId: process.env.EXPO_PUBLIC_IOS_GOOGLE_CLIENT_ID,
        // We do NOT set androidClientId to the Android-specific ID because that forces a flow
        // that doesn't support custom/https redirects in the same way.
        // By using the web client ID, we force the browser-based flow which accepts our redirect URI.
        androidClientId: GOOGLE_CLIENT_ID,
        redirectUri: 'https://interestedparticipant.org/oauthredirect',
        responseType: ResponseType.Token,
    });

    useEffect(() => {
        loadUser();
    }, []);

    useEffect(() => {
        if (response?.type === 'success') {
            const { authentication } = response;
            fetchUserInfo(authentication?.accessToken);
        }
    }, [response]);

    // Manual listener for the custom redirect because useAuthRequest might miss the scheme change
    useEffect(() => {
        const handleUrl = (event: { url: string }) => {
            const url = event.url;
            console.log('AuthContext: Received URL:', url); // DEBUG LOG

            // Handle only if it looks like our redirect
            if (url.includes('oauthredirect')) {
                let token = '';

                // Check hash first
                if (url.includes('#')) {
                    const hash = url.split('#')[1];
                    const params = new URLSearchParams(hash);
                    token = params.get('access_token') || '';
                }

                // If not in hash, check query
                if (!token && url.includes('?')) {
                    const search = url.split('?')[1];
                    const params = new URLSearchParams(search);
                    token = params.get('access_token') || '';
                }

                console.log('AuthContext: Parsed token:', token ? 'Found' : 'Not found'); // DEBUG LOG

                if (token) {
                    fetchUserInfo(token);
                }
            }
        };

        // Check initial URL if app was closed
        Linking.getInitialURL().then(url => {
            if (url) handleUrl({ url });
        });

        const subscription = Linking.addEventListener('url', handleUrl);
        return () => {
            subscription.remove();
        };
    }, []);

    async function loadUser() {
        try {
            const json = await AsyncStorage.getItem(STORAGE_KEY);
            if (json) {
                setUser(JSON.parse(json));
            }
        } catch (e) {
            console.error('Failed to load user', e);
        } finally {
            setIsLoading(false);
        }
    }

    async function fetchUserInfo(token?: string) {
        if (!token) return;
        try {
            const res = await fetch('https://www.googleapis.com/oauth2/v2/userinfo', {
                headers: { Authorization: `Bearer ${token}` }
            });
            const userDetails = await res.json();
            const authorizedUser = {
                email: userDetails.email,
                name: userDetails.name,
                picture: userDetails.picture,
                idToken: token // Store access token for API calls
            };
            setUser(authorizedUser);
            await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(authorizedUser));
        } catch (e) {
            console.error(e);
        }
    }

    const signIn = async () => {
        await promptAsync();
    };

    const signInDev = async () => {
        const devUser = {
            email: 'dev@example.com',
            name: 'Developer',
            picture: 'https://via.placeholder.com/150',
            idToken: 'dev-token',
        };
        setUser(devUser);
        await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(devUser));
    };

    const signOut = async () => {
        setUser(null);
        await AsyncStorage.removeItem(STORAGE_KEY);
    };

    return (
        <AuthContext.Provider value={{ user, signIn, signInDev, signOut, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
}
