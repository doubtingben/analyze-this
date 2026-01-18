import { Platform } from 'react-native';
import Constants from 'expo-constants';

const getLocalApiUrl = () => {
    if (Constants.expoConfig?.hostUri) {
        const host = Constants.expoConfig.hostUri.split(':')[0];
        return `http://${host}:8000`;
    }
    return Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
};

const LOCAL_API_URL = getLocalApiUrl();
// Replace with actual production URL when known
const PROD_API_URL = 'https://interestedparticipant.org';

// Forcing Prod URL for preview testing as requested
export const API_URL = PROD_API_URL;
// export const API_URL = __DEV__ ? LOCAL_API_URL : PROD_API_URL;

