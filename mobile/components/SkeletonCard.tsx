import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { ARTICLE_CARD_MIN_HEIGHT } from '@/components/constants';
import { colors, radius, spacing } from '@/theme';

export function SkeletonCard() {
  const opacity = useSharedValue(0.3);

  useEffect(() => {
    opacity.value = withRepeat(
      withTiming(0.7, { duration: 600 }),
      -1,
      true,
    );
  }, [opacity]);

  const animatedStyle = useAnimatedStyle(() => ({ opacity: opacity.value }));

  return (
    <Animated.View
      testID="skeleton-card"
      style={[styles.card, animatedStyle]}>
      <View style={styles.meta} />
      <View style={styles.title} />
      <View style={styles.line} />
      <View style={styles.shortLine} />
      <View style={styles.footer} />
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  card: {
    minHeight: ARTICLE_CARD_MIN_HEIGHT,
    gap: spacing.md,
    padding: spacing.lg,
    borderRadius: radius.lg,
    borderColor: colors.border.subtle,
    borderWidth: 1,
    backgroundColor: colors.background.secondary,
  },
  meta: {
    width: 88,
    height: 12,
    borderRadius: radius.sm,
    backgroundColor: colors.background.tertiary,
  },
  title: {
    width: '90%',
    height: 20,
    borderRadius: radius.sm,
    backgroundColor: colors.background.tertiary,
  },
  line: {
    width: '100%',
    height: 14,
    borderRadius: radius.sm,
    backgroundColor: colors.background.tertiary,
  },
  shortLine: {
    width: '64%',
    height: 14,
    borderRadius: radius.sm,
    backgroundColor: colors.background.tertiary,
  },
  footer: {
    marginTop: 'auto',
    width: '38%',
    height: 10,
    borderRadius: radius.sm,
    backgroundColor: colors.background.tertiary,
  },
});
