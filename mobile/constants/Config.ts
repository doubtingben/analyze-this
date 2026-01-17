import { Platform } from 'react-native';

const LOCAL_API_URL = Platform.OS === 'android' ? 'http://10.0.2.2:8000' : 'http://localhost:8000';
// Replace with actual production URL when known
const PROD_API_URL = 'https://interestedparticipant.org';

export const API_URL = __DEV__ ? LOCAL_API_URL : PROD_API_URL;
