import type { ReactElement } from 'react';
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SymbolView } from 'expo-symbols';

import { ArticleCard } from '@/components/ArticleCard';
import { SkeletonCard } from '@/components/SkeletonCard';
import { colors, spacing, typography } from '@/theme';
import type { Article } from '@/types/article';

interface ArticleListProps {
  articles: Article[];
  isLoading: boolean;
  isRefreshing?: boolean;
  isFetchingNextPage?: boolean;
  hasNextPage?: boolean;
  header?: ReactElement | null;
  emptyTitle: string;
  emptyBody: string;
  onEndReached?: () => void;
  onRefresh?: () => void;
  error?: boolean;
  onRetry?: () => void;
}

export function ArticleList({
  articles,
  isLoading,
  isRefreshing = false,
  isFetchingNextPage = false,
  hasNextPage = false,
  header,
  emptyTitle,
  emptyBody,
  onEndReached,
  onRefresh,
  error = false,
  onRetry,
}: ArticleListProps) {
  if (isLoading) {
    return (
      <FlatList
        contentContainerStyle={styles.content}
        data={Array.from({ length: 5 }, (_, index) => index)}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
        keyExtractor={(item) => `skeleton-${item}`}
        ListHeaderComponent={header}
        renderItem={() => <SkeletonCard />}
      />
    );
  }

  return (
    <FlatList
      testID="article-list"
      contentContainerStyle={styles.content}
      data={articles}
      ItemSeparatorComponent={() => <View style={styles.separator} />}
      keyExtractor={(article) => article.id}
      ListEmptyComponent={
        <View style={styles.empty}>
          <SymbolView
            testID="empty-state-illustration"
            name={{
              ios: error ? 'wifi.exclamationmark' : 'newspaper',
              android: error ? 'wifi_off' : 'article',
              web: error ? 'wifi_off' : 'article',
            }}
            tintColor={error ? colors.warning : colors.accent}
            size={42}
          />
          <Text style={styles.emptyTitle}>
            {error ? 'Unable to load articles' : emptyTitle}
          </Text>
          <Text style={styles.emptyBody}>{emptyBody}</Text>
          {error && onRetry ? (
            <Pressable
              accessibilityRole="button"
              onPress={onRetry}
              style={styles.retry}>
              <Text style={styles.retryText}>Retry</Text>
            </Pressable>
          ) : null}
        </View>
      }
      ListFooterComponent={
        isFetchingNextPage ? (
          <ActivityIndicator
            color={colors.accent}
            style={styles.footerSpinner}
          />
        ) : null
      }
      ListHeaderComponent={header}
      onEndReached={() => {
        if (hasNextPage && !isFetchingNextPage) onEndReached?.();
      }}
      onEndReachedThreshold={0.3}
      refreshControl={
        onRefresh ? (
          <RefreshControl
            onRefresh={onRefresh}
            refreshing={isRefreshing}
            tintColor={colors.accent}
          />
        ) : undefined
      }
      renderItem={({ item, index }) => (
        <ArticleCard article={item} index={index} />
      )}
    />
  );
}

const styles = StyleSheet.create({
  content: {
    flexGrow: 1,
    padding: spacing.lg,
    paddingBottom: spacing['3xl'],
  },
  separator: {
    height: spacing.md,
  },
  empty: {
    alignItems: 'center',
    gap: spacing.sm,
    paddingHorizontal: spacing.xl,
    paddingTop: 80,
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
  footerSpinner: {
    padding: spacing.xl,
  },
});
