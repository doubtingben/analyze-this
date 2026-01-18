import { createContext, useContext, useState, useEffect } from 'react';
import * as Google from 'expo-auth-session/providers/google';
import * as WebBrowser from 'expo-web-browser';
import AsyncStorage from '@react-native-async-storage/async-storage';

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

    const [request, response, promptAsync] = Google.useAuthRequest({
        // Use the Web Client ID for all platforms to support HTTPS redirects
        clientId: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID,
        iosClientId: process.env.EXPO_PUBLIC_IOS_GOOGLE_CLIENT_ID,
        // We do NOT set androidClientId to the Android-specific ID because that forces a flow
        // that doesn't support custom/https redirects in the same way.
        // By using the web client ID, we force the browser-based flow which accepts our redirect URI.
        androidClientId: process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID,
        redirectUri: 'https://interestedparticipant.org/oauthredirect',
    });

    useEffect(() => {
        loadUser();
    }, []);

    useEffect(() => {
        if (response?.type === 'success') {
            const { authentication } = response;
            // We can use authentication.idToken
            // Verify with backend or just use it. 
            // For this task, we assume we send IT to backend.
            fetchUserInfo(authentication?.accessToken);
        }
    }, [response]);

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
                idToken: response?.type === 'success' ? response.authentication?.accessToken : undefined // Store access token for API calls
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

    const signOut = async () => {
        setUser(null);
        await AsyncStorage.removeItem(STORAGE_KEY);
    };

    return (
        <AuthContext.Provider value={{ user, signIn, signOut, isLoading }}>
            {children}
        </AuthContext.Provider>
    );
}
