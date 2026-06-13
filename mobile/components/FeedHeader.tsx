import { format, formatDistanceToNow } from 'date-fns';
import { LinearGradient } from 'expo-linear-gradient';
import { SymbolView } from 'expo-symbols';
import { StyleSheet, Text, View } from 'react-native';

import { colors, radius, spacing, typography } from '@/theme';

interface FeedHeaderProps {
  articleCount?: number;
  updatedAt?: number;
}

export function FeedHeader({ articleCount, updatedAt }: FeedHeaderProps) {
  return (
    <View style={styles.header}>
      <View style={styles.topRow}>
        <Text style={styles.date}>{format(new Date(), 'EEEE, MMMM d')}</Text>
        <SymbolView
          name={{
            ios: 'bell',
            android: 'notifications',
            web: 'notifications',
          }}
          tintColor={colors.text.secondary}
          size={24}
        />
      </View>
      <LinearGradient
        colors={['#7C3AED', '#2563EB']}
        end={{ x: 1, y: 0 }}
        start={{ x: 0, y: 0 }}
        style={styles.wordmark}>
        <Text style={styles.title}>Pulse</Text>
      </LinearGradient>
      <Text style={styles.subtitle}>
        {articleCount === undefined
          ? 'Your daily tech intelligence'
          : `${articleCount} articles tuned to your interests`}
      </Text>
      {updatedAt ? (
        <Text style={styles.updated}>
          Last updated{' '}
          {formatDistanceToNow(new Date(updatedAt), { addSuffix: true })}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  header: {
    gap: spacing.sm,
    padding: spacing.lg,
    paddingBottom: spacing.md,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  date: {
    color: colors.text.tertiary,
    fontFamily: typography.fontFamily.medium,
    fontSize: typography.size.sm,
  },
  wordmark: {
    alignSelf: 'flex-start',
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  title: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.bold,
    fontSize: typography.size.xl,
  },
  subtitle: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.sm,
  },
  updated: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.xs,
  },
});
