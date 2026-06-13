import { useNetworkState } from 'expo-network';
import { StyleSheet, Text, View } from 'react-native';

import { colors, spacing, typography } from '@/theme';

export function NetworkBanner({
  offlineOverride,
}: {
  offlineOverride?: boolean;
}) {
  const network = useNetworkState();
  const offline =
    offlineOverride ??
    (network.isConnected === false ||
      network.isInternetReachable === false);

  if (!offline) return null;

  return (
    <View accessibilityRole="alert" style={styles.banner}>
      <Text style={styles.text}>
        You&apos;re offline. Showing saved articles.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    alignItems: 'center',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    backgroundColor: '#713F12',
  },
  text: {
    color: '#FEF3C7',
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.xs,
  },
});
