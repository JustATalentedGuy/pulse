import { router } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';
import type { Trend } from '@/types/phase8';
import { lightHaptic } from '@/utils/haptics';

export function TrendingStrip({ trends }: { trends: Trend[] }) {
  if (trends.length === 0) return null;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>TRENDING NOW</Text>
      <ScrollView
        contentContainerStyle={styles.content}
        horizontal
        showsHorizontalScrollIndicator={false}>
        {trends.map((trend) => (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Search trend ${trend.name}`}
            key={trend.name}
            onPress={() => {
              void lightHaptic();
              router.push({
                pathname: '/search',
                params: { q: trend.name },
              });
            }}
            style={styles.chip}>
            <View style={styles.dot} />
            <Text style={styles.name}>{trend.name}</Text>
            <Text style={styles.count}>{trend.mention_count}</Text>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.sm,
    paddingBottom: spacing.md,
  },
  title: {
    paddingHorizontal: spacing.lg,
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.xs,
    letterSpacing: 1,
  },
  content: {
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border.default,
    borderRadius: radius.full,
    backgroundColor: colors.background.tertiary,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: radius.full,
    backgroundColor: colors.error,
  },
  name: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.sm,
  },
  count: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.mono,
    fontSize: typography.size.xs,
  },
});
