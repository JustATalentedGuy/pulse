import axios from 'axios';
import { SymbolView } from 'expo-symbols';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ArticleCard } from '@/components/ArticleCard';
import { DigestCard } from '@/components/DigestCard';
import { SkeletonCard } from '@/components/SkeletonCard';
import { useDigest } from '@/hooks/useDigest';
import { colors, spacing, typography } from '@/theme';
import { lightHaptic } from '@/utils/haptics';

export default function DigestScreen() {
  const digest = useDigest();
  const notGenerated =
    axios.isAxiosError(digest.error) && digest.error.response?.status === 404;

  return (
    <SafeAreaView edges={['top']} style={styles.safeArea}>
      <ScrollView contentContainerStyle={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title}>Daily Digest</Text>
          <Text style={styles.subtitle}>The strongest signals in one brief</Text>
        </View>
        {digest.isLoading ? (
          <SkeletonCard />
        ) : digest.data ? (
          <>
            <DigestCard digest={digest.data} />
            <Text style={styles.sectionTitle}>Top stories</Text>
            {digest.data.top_articles.map((article, index) => (
              <ArticleCard
                article={article}
                compact
                index={index}
                key={article.id}
              />
            ))}
          </>
        ) : (
          <View style={styles.empty}>
            <SymbolView
              name={{
                ios: notGenerated ? 'clock' : 'wifi.exclamationmark',
                android: notGenerated ? 'schedule' : 'wifi_off',
                web: notGenerated ? 'schedule' : 'wifi_off',
              }}
              tintColor={notGenerated ? colors.accent : colors.warning}
              size={42}
            />
            <Text style={styles.emptyTitle}>
              {notGenerated ? 'Today’s digest is brewing' : 'Digest unavailable'}
            </Text>
            {!notGenerated ? (
              <Pressable
                accessibilityRole="button"
                onPress={() => {
                  void lightHaptic();
                  void digest.refetch();
                }}
                style={styles.retry}>
                <Text style={styles.retryText}>Retry</Text>
              </Pressable>
            ) : null}
            <Text style={styles.emptyBody}>
              {notGenerated
                ? 'The scheduler creates it at 7:00 AM Asia/Kolkata when enriched stories are available.'
                : 'Pull down later after checking the backend connection.'}
            </Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background.primary,
  },
  content: {
    gap: spacing.md,
    padding: spacing.lg,
    paddingBottom: 100,
  },
  header: {
    gap: spacing.xs,
    paddingBottom: spacing.md,
  },
  title: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.bold,
    fontSize: typography.size['2xl'],
  },
  subtitle: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.sm,
  },
  sectionTitle: {
    marginTop: spacing.md,
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.md,
  },
  empty: {
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing['2xl'],
  },
  emptyTitle: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.md,
  },
  emptyBody: {
    color: colors.text.secondary,
    fontFamily: typography.fontFamily.regular,
    fontSize: typography.size.sm,
    lineHeight: 20,
    textAlign: 'center',
  },
  retry: {
    marginTop: spacing.sm,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.md,
    borderRadius: 14,
    backgroundColor: colors.accent,
  },
  retryText: {
    color: colors.text.primary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.sm,
  },
});
