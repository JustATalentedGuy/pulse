import { LinearGradient } from 'expo-linear-gradient';
import { StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { Digest } from '@/types/article';

export function DigestCard({ digest }: { digest: Digest }) {
  return (
    <LinearGradient
      colors={['#7C3AED', '#2563EB']}
      end={{ x: 1, y: 0 }}
      start={{ x: 0, y: 0 }}
      style={styles.border}>
      <View style={styles.card}>
        <Text style={styles.eyebrow}>DAILY DIGEST</Text>
        <Text style={styles.headline}>
          {digest.headline ?? 'Your daily intelligence brief'}
        </Text>
        <Text numberOfLines={8} style={styles.narrative}>
          {digest.narrative}
        </Text>
        <View style={styles.themes}>
          {digest.key_themes.map((theme) => (
            <View key={theme} style={styles.theme}>
              <Text style={styles.themeText}>{theme}</Text>
            </View>
          ))}
        </View>
      </View>
    </LinearGradient>
  );
}

const styles = StyleSheet.create({
  border: {
    borderRadius: radius.xl,
    padding: 1,
  },
  card: {
    gap: spacing.md,
    padding: spacing.xl,
    borderRadius: radius.xl,
    backgroundColor: colors.background.secondary,
  },
  eyebrow: {
    color: colors.accent,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.xs,
    letterSpacing: 1.2,
  },
  headline: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.md,
    lineHeight: 24,
  },
  narrative: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.sm,
    lineHeight: 21,
  },
  themes: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
  },
  theme: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: radius.full,
    backgroundColor: colors.accentSoft,
  },
  themeText: {
    color: '#C4B5FD',
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.xs,
  },
});
