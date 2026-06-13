import { useQueryClient } from '@tanstack/react-query';
import * as Haptics from 'expo-haptics';
import { useCallback, useMemo } from 'react';
import { View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { api } from '@/api/client';
import { ArticleList } from '@/components/ArticleList';
import { CategoryFilterBar } from '@/components/CategoryFilterBar';
import { FeedHeader } from '@/components/FeedHeader';
import { TrendingStrip } from '@/components/TrendingStrip';
import { useFeed } from '@/hooks/useFeed';
import { useTrends } from '@/hooks/useTrends';
import { useFeedStore } from '@/store/feedStore';
import { colors } from '@/theme';
import { uniqueArticles } from '@/utils/articles';

export default function FeedScreen() {
  const queryClient = useQueryClient();
  const selectedCategory = useFeedStore((state) => state.selectedCategory);
  const minImportance = useFeedStore((state) => state.minImportance);
  const setCategory = useFeedStore((state) => state.setCategory);
  const feed = useFeed(selectedCategory, minImportance);
  const trends = useTrends();
  const articles = useMemo(
    () => uniqueArticles(feed.data?.pages ?? []),
    [feed.data?.pages],
  );
  const total = feed.data?.pages[0]?.total;

  const refresh = useCallback(async () => {
    await Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    await Promise.allSettled([
      api.post('/ingest/trigger'),
      queryClient.invalidateQueries({ queryKey: ['feed'] }),
    ]);
    await feed.refetch();
  }, [feed, queryClient]);

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.background.primary }}>
      <ArticleList
        articles={articles}
        emptyBody="Check the API connection or choose another category."
        emptyTitle="No articles found"
        hasNextPage={feed.hasNextPage}
        header={
          <View style={{ marginHorizontal: -16 }}>
            <FeedHeader articleCount={total} updatedAt={feed.dataUpdatedAt} />
            <TrendingStrip trends={trends.data ?? []} />
            <CategoryFilterBar
              onSelect={setCategory}
              selected={selectedCategory}
            />
          </View>
        }
        isFetchingNextPage={feed.isFetchingNextPage}
        isLoading={feed.isLoading}
        error={feed.isError && articles.length === 0}
        isRefreshing={feed.isRefetching && !feed.isFetchingNextPage}
        onEndReached={() => void feed.fetchNextPage()}
        onRefresh={() => void refresh()}
        onRetry={() => void feed.refetch()}
      />
    </SafeAreaView>
  );
}
