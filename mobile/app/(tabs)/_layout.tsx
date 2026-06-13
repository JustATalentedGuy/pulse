import { BlurView } from 'expo-blur';
import * as Haptics from 'expo-haptics';
import { SymbolView } from 'expo-symbols';
import { Tabs } from 'expo-router';
import { StyleSheet } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '@/theme';

export default function TabLayout() {
  const insets = useSafeAreaInsets();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.text.tertiary,
        tabBarShowLabel: false,
        tabBarStyle: {
          position: 'absolute',
          height: 58 + insets.bottom,
          paddingBottom: insets.bottom,
          backgroundColor: 'transparent',
          borderTopColor: colors.border.subtle,
        },
        tabBarBackground: () => (
          <BlurView intensity={80} style={StyleSheet.absoluteFill} tint="dark" />
        ),
      }}>
      <Tabs.Screen
        name="index"
        listeners={{ tabPress: () => void Haptics.selectionAsync() }}
        options={{
          title: 'Feed',
          tabBarIcon: ({ color }) => (
            <SymbolView
              name={{
                ios: 'house.fill',
                android: 'home',
                web: 'home',
              }}
              tintColor={color}
              size={28}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="search"
        listeners={{ tabPress: () => void Haptics.selectionAsync() }}
        options={{
          title: 'Search',
          tabBarIcon: ({ color }) => (
            <SymbolView
              name={{
                ios: 'magnifyingglass',
                android: 'search',
                web: 'search',
              }}
              tintColor={color}
              size={27}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="ask"
        listeners={{ tabPress: () => void Haptics.selectionAsync() }}
        options={{
          title: 'Ask',
          tabBarIcon: ({ color }) => (
            <SymbolView
              name={{
                ios: 'sparkles',
                android: 'auto_awesome',
                web: 'auto_awesome',
              }}
              tintColor={color}
              size={27}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="digest"
        listeners={{ tabPress: () => void Haptics.selectionAsync() }}
        options={{
          title: 'Digest',
          tabBarIcon: ({ color }) => (
            <SymbolView
              name={{
                ios: 'newspaper.fill',
                android: 'newspaper',
                web: 'newspaper',
              }}
              tintColor={color}
              size={27}
            />
          ),
        }}
      />
      <Tabs.Screen
        name="bookmarks"
        listeners={{ tabPress: () => void Haptics.selectionAsync() }}
        options={{
          title: 'Bookmarks',
          tabBarIcon: ({ color }) => (
            <SymbolView
              name={{
                ios: 'bookmark.fill',
                android: 'bookmark',
                web: 'bookmark',
              }}
              tintColor={color}
              size={27}
            />
          ),
        }}
      />
      <Tabs.Screen name="two" options={{ href: null }} />
    </Tabs>
  );
}
