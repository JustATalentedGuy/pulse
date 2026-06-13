import { useState } from 'react';
import { Image, StyleSheet, Text, View } from 'react-native';

import { colors, radius, typography } from '@/theme';

export function SourceAvatar({
  domain,
  source,
}: {
  domain: string;
  source: string;
}) {
  const [failed, setFailed] = useState(false);
  if (failed || !domain) {
    return (
      <View style={styles.fallback}>
        <Text style={styles.initial}>{source.slice(0, 1).toUpperCase()}</Text>
      </View>
    );
  }
  return (
    <Image
      accessibilityLabel={`${source} logo`}
      onError={() => setFailed(true)}
      source={{
        uri: `https://www.google.com/s2/favicons?domain=${encodeURIComponent(domain)}&sz=64`,
      }}
      style={styles.image}
    />
  );
}

const styles = StyleSheet.create({
  image: {
    width: 20,
    height: 20,
    borderRadius: radius.sm,
  },
  fallback: {
    width: 20,
    height: 20,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radius.sm,
    backgroundColor: colors.accentSoft,
  },
  initial: {
    color: '#DDD6FE',
    fontFamily: typography.fontFamily.bold,
    fontSize: typography.size.xs,
  },
});
