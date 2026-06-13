import {
  Inter_400Regular,
  Inter_500Medium,
  Inter_600SemiBold,
  Inter_700Bold,
  useFonts,
} from '@expo-google-fonts/inter';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { onlineManager, QueryClient } from '@tanstack/react-query';
import { PersistQueryClientProvider } from '@tanstack/react-query-persist-client';
import { createAsyncStoragePersister } from '@tanstack/query-async-storage-persister';
import * as Network from 'expo-network';
import { DarkTheme, Stack, ThemeProvider } from 'expo-router';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect, useState } from 'react';
import { View } from 'react-native';
import 'react-native-reanimated';

import { NetworkBanner } from '@/components/NetworkBanner';
import { usePushNotifications } from '@/hooks/usePushNotifications';

export {
  // Catch any errors thrown by the Layout component.
  ErrorBoundary,
} from 'expo-router';

export const unstable_settings = {
  // Ensure that reloading on `/modal` keeps a back button present.
  initialRouteName: '(tabs)',
};

// Prevent the splash screen from auto-hiding before asset loading is complete.
SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  usePushNotifications();
  const [loaded, error] = useFonts({
    Inter_400Regular,
    Inter_500Medium,
    Inter_600SemiBold,
    Inter_700Bold,
    SpaceMono: require('../assets/fonts/SpaceMono-Regular.ttf'),
  });
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            gcTime: 7 * 24 * 60 * 60_000,
            retry: 1,
            refetchOnWindowFocus: false,
            networkMode: 'offlineFirst',
          },
        },
      }),
  );

  // Expo Router uses Error Boundaries to catch errors in the navigation tree.
  useEffect(() => {
    if (error) throw error;
  }, [error]);

  useEffect(() => {
    if (loaded) {
      SplashScreen.hideAsync();
    }
  }, [loaded]);

  useEffect(() => {
    const subscription = Network.addNetworkStateListener((state) => {
      onlineManager.setOnline(
        state.isConnected !== false &&
          state.isInternetReachable !== false,
      );
    });
    return () => subscription.remove();
  }, []);

  if (!loaded) {
    return null;
  }

  return (
    <PersistQueryClientProvider
      client={queryClient}
      persistOptions={{
        buster: 'pulse-phase8-v1',
        maxAge: 7 * 24 * 60 * 60_000,
        persister: createAsyncStoragePersister({
          storage: AsyncStorage,
          key: 'PULSE_QUERY_CACHE',
        }),
      }}>
      <ThemeProvider value={DarkTheme}>
        <View style={{ flex: 1, backgroundColor: '#0D0D0F' }}>
          <NetworkBanner />
          <Stack>
            <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
            <Stack.Screen
              name="article/[id]"
              options={{
                headerShown: true,
                headerBackTitle: 'Feed',
                headerStyle: { backgroundColor: '#0D0D0F' },
                headerTintColor: '#F0EFE9',
                title: 'Article',
              }}
            />
            <Stack.Screen
              name="quiz/[articleId]"
              options={{
                headerShown: true,
                headerBackTitle: 'Article',
                headerStyle: { backgroundColor: '#0D0D0F' },
                headerTintColor: '#F0EFE9',
                title: 'Test yourself',
              }}
            />
          </Stack>
        </View>
      </ThemeProvider>
    </PersistQueryClientProvider>
  );
}
