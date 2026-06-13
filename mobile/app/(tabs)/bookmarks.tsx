import { useMemo } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ArticleList } from '@/components/ArticleList';
import { useBookmarks } from '@/hooks/useBookmarks';
import { colors, spacing, typography } from '@/theme';
import { uniqueArticles } from '@/utils/articles';

export default function BookmarksScreen() {
  const bookmarks = useBookmarks();
  const articles = useMemo(
    () => uniqueArticles(bookmarks.data?.pages ?? []),
    [bookmarks.data?.pages],
  );

  return (
    <SafeAreaView edges={['top']} style={styles.safeArea}>
      <ArticleList
        articles={articles}
        emptyBody="Bookmark useful articles from the feed and they will stay here."
        emptyTitle="Nothing saved yet"
        hasNextPage={bookmarks.hasNextPage}
        header={
          <View style={styles.header}>
            <Text style={styles.title}>Bookmarks</Text>
            <Text style={styles.subtitle}>Your save-for-later reading list</Text>
          </View>
        }
        isFetchingNextPage={bookmarks.isFetchingNextPage}
        isLoading={bookmarks.isLoading}
        error={bookmarks.isError && articles.length === 0}
        isRefreshing={bookmarks.isRefetching}
        onEndReached={() => void bookmarks.fetchNextPage()}
        onRefresh={() => void bookmarks.refetch()}
        onRetry={() => void bookmarks.refetch()}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background.primary,
  },
  header: {
    gap: spacing.xs,
    paddingBottom: spacing.xl,
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
});
