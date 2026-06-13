import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { useEffect } from 'react';
import { Platform } from 'react-native';

import { api } from '@/api/client';

export function usePushNotifications() {
  useEffect(() => {
    const pushEnabled =
      process.env.EXPO_PUBLIC_PUSH_NOTIFICATIONS_ENABLED === 'true';
    if (!pushEnabled || Platform.OS === 'web' || !Device.isDevice) return;

    let cancelled = false;
    const register = async () => {
      try {
        Notifications.setNotificationHandler({
          handleNotification: async () => ({
            shouldPlaySound: false,
            shouldSetBadge: false,
            shouldShowBanner: true,
            shouldShowList: true,
          }),
        });
        if (Platform.OS === 'android') {
          await Notifications.setNotificationChannelAsync('pulse', {
            name: 'Pulse',
            importance: Notifications.AndroidImportance.DEFAULT,
          });
        }
        const current = await Notifications.getPermissionsAsync();
        const permission =
          current.status === 'granted'
            ? current
            : await Notifications.requestPermissionsAsync();
        if (permission.status !== 'granted' || cancelled) return;

        const projectId =
          process.env.EXPO_PUBLIC_EAS_PROJECT_ID ??
          Constants.expoConfig?.extra?.eas?.projectId ??
          Constants.easConfig?.projectId;
        if (!projectId) return;

        const token = await Notifications.getExpoPushTokenAsync({ projectId });
        if (!cancelled) {
          await api.post('/user/push-token', { token: token.data });
        }
      } catch (error) {
        console.warn('[Push registration skipped]', error);
      }
    };

    void register();
    return () => {
      cancelled = true;
    };
  }, []);
}
