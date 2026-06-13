import axios from 'axios';
import Constants from 'expo-constants';
import { Platform } from 'react-native';

import { resolveApiBaseUrl } from '@/utils/apiUrl';

const apiUrl = resolveApiBaseUrl({
  autoHost: process.env.EXPO_PUBLIC_API_AUTO_HOST !== 'false',
  configuredNativeUrl: process.env.EXPO_PUBLIC_API_URL,
  configuredWebUrl: process.env.EXPO_PUBLIC_API_WEB_URL,
  devServerHostUri: Constants.expoConfig?.hostUri,
  isDev: __DEV__,
  platform: Platform.OS,
  port: process.env.EXPO_PUBLIC_API_PORT ?? '8000',
});
const apiKey = process.env.EXPO_PUBLIC_API_KEY;
const configuredTimeout = Number(
  process.env.EXPO_PUBLIC_API_TIMEOUT_MS ?? '10000',
);

export const api = axios.create({
  baseURL: apiUrl,
  headers: { 'X-API-Key': apiKey },
  timeout: Number.isFinite(configuredTimeout)
    ? configuredTimeout
    : 10000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error(
      '[API Error]',
      error.response?.status ?? 'network',
      error.config?.url,
    );
    return Promise.reject(error);
  },
);
