import { useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ArticleList } from '@/components/ArticleList';
import { SearchBar } from '@/components/SearchBar';
import { SearchModeSelector } from '@/components/SearchModeSelector';
import { useBookmarks } from '@/hooks/useBookmarks';
import { useSearch } from '@/hooks/useSearch';
import { colors, spacing, typography } from '@/theme';
import type { SearchMode } from '@/types/article';
import { uniqueArticles } from '@/utils/articles';

export default function SearchScreen() {
  const params = useLocalSearchParams<{ q?: string | string[] }>();
  const routedQuery = Array.isArray(params.q) ? params.q[0] : params.q;
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<SearchMode>('hybrid');
  const search = useSearch(query, mode);
  const bookmarks = useBookmarks();
  const normalized = query.trim();
  const showingBookmarks = normalized.length < 2;
  const articles = useMemo(
    () =>
      showingBookmarks
        ? uniqueArticles(bookmarks.data?.pages ?? [])
        : search.data?.results ?? [],
    [bookmarks.data?.pages, search.data?.results, showingBookmarks],
  );

  useEffect(() => {
    if (routedQuery) setQuery(routedQuery);
  }, [routedQuery]);

  return (
    <SafeAreaView edges={['top']} style={styles.safeArea}>
      <SearchBar onChangeText={setQuery} value={query} />
      <SearchModeSelector onSelect={setMode} selected={mode} />
      <ArticleList
        articles={articles}
        emptyBody={
          showingBookmarks
            ? 'Your recent bookmarks will appear here before you search.'
            : 'Try another model, company, technique, or article title.'
        }
        emptyTitle={showingBookmarks ? 'Search your intelligence feed' : 'No matches'}
        header={
          <View style={styles.header}>
            <Text style={styles.label}>
              {showingBookmarks
                ? 'RECENT BOOKMARKS'
                : `${search.data?.total ?? 0} ${mode.toUpperCase()} RESULTS`}
            </Text>
          </View>
        }
        isLoading={showingBookmarks ? bookmarks.isLoading : search.isLoading}
        error={
          showingBookmarks
            ? bookmarks.isError && articles.length === 0
            : search.isError && articles.length === 0
        }
        onRetry={() =>
          void (showingBookmarks ? bookmarks.refetch() : search.refetch())
        }
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
    paddingBottom: spacing.md,
  },
  label: {
    color: colors.text.tertiary,
    fontFamily: typography.fontFamily.semibold,
    fontSize: typography.size.xs,
    letterSpacing: 1,
  },
});
